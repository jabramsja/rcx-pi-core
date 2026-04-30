# Wave 1: Pipeline/Control-Surface Consolidated Findings

Date: 2026-03-31
Status: OPEN
Surface: `mu/tools/executors/`, `mu/tools/agents/`, `mu/tools/checks/`, `mu/tools/observability/`, `mu/tools/hooks/`
Supersedes: 6 files (see Archive section)

---

## Cluster A — Pipeline Validation (CRITICAL/HIGH) — 5 items

### A1. [CRITICAL] Phase B accepts invalid routing tokens and unlocked plans
- **File:** `mu/tools/executors/phase_b_executor.py:380`
- `validate_inputs()` only logs warnings for wrong routing tokens (ROUTE_PHASE_A) and unlocked plans. Execution continues.
- **Fix:** Make validation errors fatal unless explicit `--force` flag.

### A2. [HIGH] Closeout attestation authorizes GO with no behavioral proof
- **File:** `mu/tools/checks/check_closeout_attestation.py:174`
- Generated attestation reports `go_authorized: true` with only git-derived proofs, zero BEHAVIORAL entries.
- **Fix:** Require at least one BEHAVIORAL proof entry for GO. Coupled with A3.

### A3. [HIGH] Gate 10 never supplies validation results to attestation
- **File:** `mu/tools/agents/meta_bridge_supervisor.py:783`
- Gate 10 runs attestation checker with `--generate --json` only. Does not forward validation-gate results.
- **Fix:** Gate 10 must pass validation results to attestation generator.

### A4. [HIGH] Phase B sweeps unrelated dirty-worktree files into handoff
- **File:** `mu/tools/executors/phase_b_executor.py:199`
- `_collect_changed_files()` returns all dirty worktree files, not just wave-scoped. Supervisor sees unrelated files.
- **Fix:** Filter against `files_to_stage` from routing record.

### A5. [HIGH] Gate 10 can't authorize non-receipt-chain control-surface waves
- **File:** `mu/tools/agents/meta_bridge_supervisor.py:787`
- Only emits gate-style proofs, insufficient for control-surface authorization.
- **Fix:** Add control-surface proof type to Gate 10 output.

---

## Cluster B — Commit Executor / Adapters — 4 items

### B1. [MEDIUM] Streaming adapter timeouts orphan child processes
- **File:** `mu/tools/agents/bridge_adapters.py:255`
- Timeout kills parent but child process may survive.
- **Fix:** Process group kill or explicit child cleanup.

### B2. [MEDIUM] Missing indicator collector treated as success
- **File:** `mu/tools/executors/commit_executor.py:373`
- Missing collector silently succeeds instead of failing closed.
- **Fix:** Fail closed when collector is missing.

### B3. [LOW] force_add_files denylist case-sensitive on macOS
- **File:** `mu/tools/executors/commit_executor.py:147`
- macOS filesystem is case-insensitive; denylist should normalize.
- **Fix:** Case-fold comparison.

### B4. [LOW] Commit executor comment contradicts receipt authority chain
- **File:** `mu/tools/executors/commit_executor.py:460`
- Comment says handoff receipt is authoritative, but runtime correctly uses supervisor receipt.
- **Fix:** Update comment to match runtime behavior.

---

## Cluster C — Control Surface Wiring — 6 items

### C1. [MEDIUM] Closeout attestation not wired into pre-commit hook
- **File:** `mu/tools/hooks/pre-commit-doc-check`
- Attestation is generated but not enforced mechanically.
- **Fix:** Wire `check_closeout_attestation.py` into hook or commit_executor step.

### C2. [MEDIUM] Control surface invariant checker not wired into pipeline
- **File:** `mu/tools/checks/check_control_surface_invariants.py`
- Checker exists with tests but is not called by any gate.
- **Fix:** Wire into supervisor gate or pre-commit hook.

### C3. [MEDIUM] INV-2 control-surface checker spoofable by dummy if-branches
- **File:** `mu/tools/checks/check_control_surface_invariants.py:150`
- **Fix:** Structural validation rather than text matching.

### C4. [MEDIUM] Bridge adapter hardcoded review mode in some paths
- **File:** `mu/tools/agents/bridge_adapters.py`
- May still use review mode for implementer invocations.
- **Fix:** Audit all bridge adapter call sites.

### C5. [MEDIUM] meta_bridge_client doesn't validate supervisor envelope schema
- **File:** `mu/tools/agents/meta_bridge_client.py`
- Client trusts supervisor envelope without validation.
- **Fix:** Add envelope schema validation.

### C6. [LOW] executor_config.json not in control-surface detection set
- **File:** `mu/tools/checks/check_control_surface_invariants.py:34`
- **Fix:** Add to detection set.

---

## Cluster D — Executor / Dispatcher — 4 items

### D1. [MEDIUM] Dialectic executor max_rounds hard-stops after 1 attempt
- **File:** `mu/tools/executors/dialectic_executor.py:137`
- Advertises `max_rounds` config but always stops after one bridge attempt.
- **Fix:** Implement actual round loop or remove dead config.

### D2. [MEDIUM] Re-entry refresh doesn't propagate deferred packet paths
- **File:** `mu/tools/executors/phase_b_executor.py:1488`
- Newly-created deferred packets not fed back into supervisor package.
- **Fix:** Propagate paths on re-entry.

### D3. [MEDIUM] Phase B classification logs contaminate JSON stdout
- **File:** `mu/tools/executors/phase_b_executor.py:196`
- Unconditional finding-classification logs pollute machine-readable output.
- **Fix:** Redirect classification logs to stderr.

### D4. [MEDIUM] Dispatcher retry surface lacks regression coverage
- **File:** `mu/tools/executors/executor_dispatch.py`
- `--retries` and held-status paths have no direct tests.
- **Fix:** Add regression tests for retry/held-status paths.

---

## Cluster E — Observability / Hooks — 8 items

### E1. [P2] BRIDGE_ZERO_OUTPUT_TIMEOUT_S should be 450s, not 1200s
- **File:** `mu/tools/agents/bridge_supervisor.py`
- Source: PR #701 bot comment. 1200s disables the watchdog since turn wall timeout is lower.
- **Fix:** Set to 450s (below turn timeout).

### E2. [LOW] Zero-output watchdog doesn't fire before wall timeout
- **File:** `mu/tools/agents/bridge_supervisor.py:89`
- Related to E1 — watchdog timing mismatch.
- **Fix:** Ensure watchdog < wall timeout after E1 fix.

### E3. [LOW] Timeout override parser accepts non-finite values
- **File:** `mu/tools/agents/bridge_supervisor.py:92`
- **Fix:** Reject NaN/Inf in parser.

### E4. [LOW] Dashboard misclassifies pre-commit vs post-merge supervisor
- **File:** `mu/tools/observability/pipeline_dashboard.py:68`
- Source: PR #701 bot comment (P3). Phase detector treats all `meta_bridge_supervisor` as post-merge.
- **Fix:** Distinguish by process args or context.

### E5. [LOW] ~~jq `last(3)` dead logic + terminal escape injection~~ **LANDED PR #843 + deferred-consolidation-e5-e6-closeout-2026-04-30**
- **File:** `mu/tools/observability/_pane_prci.sh`
- Current source uses jq `.[-3:][]` for recent bot comments and sanitizes displayed bot text for ESC/C0/DEL/C1 controls before pane rendering.
- **Proof:** `mu/tests/tools/test_pane_prci_observability.py` covers empty/short/long comment selection, escape sanitization, and C1 control stripping.

### E6. [LOW] ~~PR number not validated as numeric in gh API path~~ **LANDED PR #843**
- **File:** `mu/tools/observability/_pane_prci.sh`
- Current source rejects empty and non-numeric PR identifiers before the review-comments API path.
- **Proof:** `mu/tests/tools/test_pane_prci_observability.py` covers both non-numeric and empty PR inputs without invoking `gh api`.

### E7. [LOW] Hook tests have vacuous-pass guards
- **File:** `mu/tests/tools/test_validate_agent_compliance.py:1032`
- `if stdout:` guard creates path where test passes without checking anything.
- **Fix:** Remove vacuous guard or assert stdout non-empty.

### E8. [LOW] Phase B executor gitignore comment wrong
- **File:** `mu/tools/executors/phase_b_executor.py:1404`
- Comment says `.claude/hooks/` is gitignored but it is explicitly un-ignored.
- **Fix:** Correct comment.

---

## Cluster F — Stale Doc/Report Comments — BULK RESOLVE

The following items from the original files are meta-findings about other reports containing stale text. These resolve automatically when the corresponding code fixes land and reports are archived. No separate code changes needed.

- ~15 items about commit_pipeline_automation_plan stale schema descriptions
- ~10 items about sweep packet unchecked acceptance checkboxes
- ~5 items about deferred packet self-referential inflation
- Blocking hardening report stale markers
- Stale entries in executor_config.json (advisory, not load-bearing)
- shared_agent_utils unused imports (dead code)

**Action:** Archive source reports after Wave 1 code fixes land. Stale doc refs resolve on archive.

---

## Archive

These files are superseded by this consolidated document:

| Original File | Unique Items | Disposition |
|---|---|---|
| `commit_pipeline_hardening_2026-03-23.md` | 11 → all captured above | Archive |
| `commit_pipeline_bridge_r1_findings_2026-03-23.md` | 10 open → all captured above (#5 already fixed) | Archive |
| `commit_pipeline_automation_plan_2026-03-22_bridge_nonblockers.md` | 33 → ~8 unique + 25 meta/stale | Archive |
| `next-codex-post-redteam-phase-a-structural-gap-swe-2026-03-30_bridge_nonblockers.md` | 30 → 6 unique + 24 duplicates | Archive |
| `deferred-cleanup-2026-03-29_bridge_nonblockers.md` | 6 → 4 unique + 2 meta | Archive |
| `deferred-nonpipeline-fixes-2026-03-29_bridge_nonblockers.md` | 6 → 4 unique + 2 doc-only | Archive |

**Total: 97 raw findings → 27 unique actionable items + ~70 duplicates/meta/stale**
