# Control-Surface Adversarial Hardening Blockers

Date: 2026-03-23
Updated: 2026-03-24
Status: RESOLVED (2026-03-29, deferred_cleanup wave)
Source: Bridge R1-R4 Codex review findings (phase-b-stabilization-r1 through r4)
Wave: control-surface-live-fixes (BOOTSTRAP_PHASE_B_EXCEPTION)

## Context

Bridge convergence loop ran 4 rounds. Core runtime defects were fixed (receipt uniqueness, re-entry fail-closed, bridge_status refresh, blocker acknowledgment, implementer process-group supervision). Bridge reviewer continued finding adversarial hardening gaps at each round. These are real observations about theoretical weaknesses, not runtime control-flow defects.

## OPEN Items

### ~~1. Phase B input validation is non-fatal (R4 finding 1, critical)~~ — FIXED 2026-03-24 (re-verified)

- Routing validation is now fatal in `run_phase_b()`: wrong routing token returns error at validate_inputs
- Only `force=True` (--bootstrap-exception) bypasses this gate
- Prior "fix" left the silent rewrite in place; bridge R1 re-found it; now truly removed
- Tests: `TestRoutingValidationNotBypassed` (6 tests)

### 2. Closeout attestation accepts control-surface GO without test-execution BEHAVIORAL proof (R4 finding 2, critical) — FIXED

- `check_closeout_attestation.py:215-227` — `validate_attestation` now requires BEHAVIORAL validation proof with "validation" in claim for control-surface waves
- Gate 10 now supplies validation commands to attestation generator via `--validation-commands` (fix #3)
- **Proven by 6 live pipeline runs (PRs #682-#687):** BEHAVIORAL proof entries are generated and accepted end-to-end

### ~~3. Gate 10 cannot provide behavioral proof to attestation (R4 finding 3, high)~~ — FIXED 2026-03-24

- Gate 10 now collects validation results and passes `--validation-commands` to attestation generator
- Fixed `r.message` → `r.error` (ValidationResult has `error` field, not `message`) which was causing AttributeError on control-surface waves
- Tests: `TestValidationResultFieldAccess` (3 tests) in test_meta_bridge_supervisor.py

### ~~4. Phase B sweeps unrelated dirty-worktree files into commit handoff~~ — FIXED 2026-03-24

- `_collect_wave_owned_files` now accepts plan-declared + implementer-tracked file sets
- Implementer changes are tracked via pre/post git diff snapshot
- Falls back to prefix-based filtering only when no explicit tracking is available

### ~~5. INV-2 AST check is still spoofable by synthetic if-blocks~~ — FIXED 2026-03-24

- INV-2 now verifies `invoke_implementer` is called INSIDE the RC/NO_GO if-branch specifically
- Also accepts Pattern B: invoke_implementer at loop top + continue in RC/NO_GO branch (re-entry loop)
- Pattern B further tightened: only accepts `invoke_implementer` as a direct statement in the for-body (not nested inside an unrelated if-branch), preventing spoofing via dummy branches

### ~~6. `executor_config.json` not in control-surface detection set~~ — FIXED (prior wave)

- Added to `CONTROL_SURFACE_FILES` along with `executor_common.py` and `executor_dispatch.py`
- `bridge_adapters.py` also added (2026-03-24)

### ~~7. Streaming adapter timeouts still orphan children in reviewer path (R4 finding 7, medium)~~ — FIXED 2026-03-24

- `bridge_adapters.py:265,306,327` — `_run_adapter_streaming` now uses `start_new_session=True` + `os.killpg` for complete process group cleanup on timeout

## Additional Fixes (2026-03-24, session 2)

- **Path traversal in load_plan_packet:** `resolve() + is_relative_to()` containment check added. Tests: `TestLoadPlanPacketPathTraversal` (3 tests).
- **Gate 10 field name bugs:** `att_data.get("go_authorized")` → `att_data.get("authorized")`, `att_data.get("blockers")` → `att_data.get("attestation", {}).get("blockers", [])`. Gate 10 was always reporting attestation failure even on success due to reading wrong JSON nesting level. Tests: updated mock in `test_receipt_chain_validation_command_in_gate10_output`.
- **Classification logs contaminate JSON stdout:** `print()` in `_classify_findings` redirected to stderr.
- **Envelope schema validation:** `run_meta_bridge_package()` now validates required fields (decision, summary, status) before constructing `SupervisorResult`, with defensive `getattr` for optional fields. Tests: `TestEnvelopeSchemaValidation` (2 tests).
- **Dead SCRIPT_DIR in commit_executor:** Removed (unused).
- **Misleading comment in commit_executor:** Fixed to reflect supervisor receipt as runtime authority.
- **Dialectic executor max_rounds:** Default changed from 3 to 1 (single-pass by design).

## Additional Fixes (2026-03-24, session 1)

- **pytest failure now blocks commit_ready:** Final pytest gate added after bridge convergence, before staging/supervisor. Tests must pass or executor returns error.
- **INV-1 strengthened:** Now verifies implementer positively calls `bridge_adapters.run_adapter()`, not just absence of `bridge_supervisor`
- **INV-4 broadened:** Now detects all forms of heuristic receipt discovery (iterdir, listdir, glob, scandir), not just `sorted(iterdir())`
- **bridge_adapters.py added to CONTROL_SURFACE_FILES:** Changes to the adapter layer now trigger control-surface review mode

## Prior Findings Already Fixed

- Receipt UUID uniqueness (R1)
- Re-entry restage fail-closed (R1)
- Bridge_status refresh on re-entry (R1)
- Attestation GO enforced via validate_attestation (R1)
- Gate 9 repo-only, no external memory (R1)
- INV-5 checks meta_bridge_task.txt (R2)
- Empty receipt rejection in commit_executor (R2)
- BEHAVIORAL proof required for changed_files (R2)
- lstrip -> removeprefix path normalization (SDK agents)
- CLAUDE.md manual merge instruction removed (pre-commit)
- Blocker acknowledgment in phase_b_executor (pre-commit)
- Anti-cheat markers for pre-push-fast (pre-commit)
- AST-aware INV-2 (replaces substring scan) (R4 — partial, now fully tightened)
- Implementer process-group supervision start_new_session + os.killpg (R4 — non-streaming path)
