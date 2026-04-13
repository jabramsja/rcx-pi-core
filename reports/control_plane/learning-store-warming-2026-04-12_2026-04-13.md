# Learning-Store-Warming-2026-04-12 (Item B: Subagent Warming)

Date: 2026-04-13
Status: Phase B (implementation-complete, bridge-converged)
Phase-A-Lock: LOCKED
Task: [PIPELINE-RECOVERY]
Wave ID: learning-store-warming-2026-04-12
Purpose: Wire learning store patterns into SDK agent and implementer prompts so subagents benefit from accumulated failure/fix knowledge.

## 1. Scope

Subagent warming: inject learning store patterns into SDK agent and implementer prompts via a single `load_relevant_learnings()` function in `recovery_gate.py`.

### Files in scope

- `mu/tools/executors/recovery_gate.py` -- new `load_relevant_learnings(agent_name, files, repo_root)` function. Reads two existing data sources owned by this file: (1) `learned_patterns.json` via `_load_learning_store()` (promoted patterns with full metadata), (2) `FIXED`-format entries from `.claude/rules/learning.md` via `_load_session_fixed_entries()` (session-captured fixes only — this function parses `FIXED | fingerprint | action` lines, NOT `PIPELINE | fingerprint | refs` lines). Sanitizes formatted output via a new local `_sanitize_learning_output(text, max_len)` helper (stdlib-only: `re` already imported, adds `unicodedata` which is stdlib). This respects the file's declared import constraint ("only stdlib + executor_common") and avoids coupling executor-side code to `tools.runners.shared_agent_utils`, which is a runner bootstrap module with import-time side effects (env clearing, SDK monkey-patching) that must not be imported into executors.
- `mu/tools/runners/run_review.py` -- add `--no-learning` CLI flag (independent of `--no-memory`), call `load_relevant_learnings()` at prompt construction when `use_learning=True` (default) and not in report-packet review mode (`build_report_packet_context(self.files)` returns empty). Import via `from tools.executors.recovery_gate import load_relevant_learnings`.
- `mu/tools/executors/phase_b_executor.py` -- compute `learning_context` once via `load_relevant_learnings()`, pass as string to `build_implementation_prompt()` at all call sites.
- `mu/tools/executors/phase_b_implementer.py` -- `build_implementation_prompt()` receives `learning_context: str = ""` kwarg and injects it. No import needed (receives pre-computed string from caller).
- `mu/tests/tools/test_recovery_gate.py` -- tests for `load_relevant_learnings()`
- `mu/tests/tools/test_run_review.py` -- tests for warming injection
- `mu/tests/tools/test_phase_b_executor.py` -- tests for `learning_context` kwarg wiring through `build_implementation_prompt()` (existing `TestBuildImplementationPrompt` class at lines 70-125 covers prompt structure; new tests prove kwarg propagation)

### Directories in scope

- `mu/tools/executors/` -- recovery_gate + phase_b_executor + phase_b_implementer
- `mu/tools/runners/` -- run_review warming wiring
- `mu/tests/tools/` -- tests

## 2. Work Items

### (a) `load_relevant_learnings(agent_name, files, repo_root)` in `recovery_gate.py`

- Reads `learned_patterns.json` via existing `_load_learning_store(repo_root)`
- Reads `FIXED`-format entries from `.claude/rules/learning.md` via existing `_load_session_fixed_entries(repo_root)` (PR #768). Important format distinction: this function's regex (`_FIXED_ENTRY_RE`) parses only `FIXED | fingerprint: \`...\` | action: \`...\`` lines written by the Claude session `capture-learning.sh` hook. It does NOT parse `PIPELINE | fingerprint: \`...\` | refs: N` lines written by `_export_to_learning_md()` during cross-pollination. This is intentional: PIPELINE entries are downstream echoes of JSON store data, so `_load_learning_store()` already captures those patterns with richer metadata (failure_class, action, timestamps, success_count). Parsing them again from learning.md would be redundant.
- Filters JSON entries by `failure_class` where the taxonomy supports meaningful subsetting. **Taxonomy limitation:** The `FailureClass` enum (`recovery_gate.py:45-68`) models 17 pipeline-recovery conditions (stale locks, timeouts, staging conflicts, test failures, merge conflicts, etc.). It does NOT model agent-domain concerns (security, complexity, structural correctness). The design doc (`PipelineRecovery.v0.md:280`) aspirationally describes domain-level filtering ("adversary gets security-related learnings, expert gets complexity learnings"), but the current taxonomy cannot distinguish these categories. Extending the taxonomy is out of scope for this enabler wave.
- **Filtering strategy given this taxonomy (explicit scope-down from design doc):** `PipelineRecovery.v0.md:280` aspirationally requires domain-level filtering ("adversary gets security-related learnings, expert gets complexity learnings"). This wave formally scopes down to pipeline-recovery-only filtering because the `FailureClass` enum models only pipeline-recovery conditions — it has no domain-level categories (security, complexity, structural correctness) to filter on. Domain-level taxonomy extension is deferred (see Section 3 constraint). Within this scoped-down contract: `implementer`, `grounding`, and `fuzzer` receive pipeline-subset filtering — they have distinct execution roles where specific failure classes produce more actionable learnings than others. All other agents receive unfiltered pipeline-recovery context because the taxonomy cannot distinguish domain-relevant subsets for them. This is an acknowledged taxonomy limitation with a documented deferral path, not a claim that unfiltered delivery satisfies the design doc's relevance contract. Static mapping:
  ```python
  _AGENT_FAILURE_CLASS_MAP: dict[str, list[str] | None] = {
      # Implementation agents — pipeline-subset: only failure classes
      # that produce actionable learnings for build/test execution
      "implementer":      ["test_failure", "git_staging_conflict", "process_timeout",
                           "implementer_stale", "needs_phase_b", "mixed_staging"],
      # Depth agents — pipeline-subset: test/edge-case execution focus
      "grounding":        ["test_failure", "needs_phase_b", "unknown_error"],
      "fuzzer":           ["test_failure", "unknown_error", "process_timeout"],
      # All other agents — unfiltered (SCOPE-DOWN): taxonomy has no
      # domain-level categories (security, complexity, etc.) to filter on.
      # Deferred: domain-level FailureClass extension per PipelineRecovery.v0.md:280.
      "verifier":         None,
      "adversary":        None,
      "expert":           None,
      "structural-proof": None,
      "translator":       None,
      "visualizer":       None,
      "advisor":          None,
  }
  ```
  `None` = unfiltered (all entries). List = include only entries whose `failure_class` field matches one of the listed values. Unknown agent names default to unfiltered.
- FIXED entries (from `_load_session_fixed_entries`) included unfiltered for all agents — they contain only `fingerprint` and `action` (no `failure_class` metadata), so domain filtering is not applicable. These are session-captured fixes only, not pipeline cross-pollination echoes (see format distinction above).
- Budget: JSON entries first (filtered, sorted by `updated_at` descending — higher signal), then FIXED entries in reverse file order (append-only file, so last = most recent; these entries expose only `fingerprint` and `action`, no timestamp). Hard cap: 4000 characters (`len()` measured, ≈1000 tokens). Truncate at entry boundaries (never split an entry mid-text).
- **Sanitization:** Before returning, the formatted output is passed through a new local `_sanitize_learning_output(text, max_len=4000)` helper defined in `recovery_gate.py` itself. This is mandatory because fingerprints originate from `_extract_classifier_signal(result)[:80]` which extracts raw stderr/stdout from prior tool execution — unsanitized injection would create a prompt-injection/control-plane path. Sanitization happens inside `load_relevant_learnings()` (not at call sites) so all consumers (run_review.py, phase_b_executor.py) receive safe output by default. The helper uses only stdlib (`re` already imported, adds `import unicodedata`) and implements the complete prompt-safety sanitization suite matching all security-relevant measures from `sanitize_for_prompt` (`shared_agent_utils.py:697-764`): (1) NFKC Unicode normalization, (2) confusable-character translation (Greek/Cyrillic visual lookalikes mapped to Latin equivalents — same `_KEYWORD_CONFUSABLE_TRANSLATION` table as `sanitize_for_prompt`; prevents bypassing keyword/verdict redaction in steps 6-7 via mixed-script near-matches like Greek Α for Latin A), (3) zero-width/line-separator control character stripping (`\u200b`-`\u200d`, `\u2028`-`\u2029`, `\u2060`, `\ufeff`, VT/FF/NEL), (4) triple-backtick escaping (```` ``` ```` → `` ` ` ` ``), (5) newline/CR replacement with space, (6) instruction-like pattern redaction (word-bounded: `ignore previous`, `disregard`, `new instructions`, `system prompt`, `forget everything`, `you are now`, `override instructions`), (7) verdict-marker redaction (`VERDICT:`, `OVERALL_VERDICT:` patterns, case-insensitive — fingerprints from `_extract_classifier_signal()` contain raw stderr/stdout that may include verdict-shaped strings from subprocess output; redact to prevent prompt-shaping payloads from reaching agent/implementer prompt parsing), (8) truncation to `max_len` AFTER sanitization (prevents smuggling past truncation boundary). **Why the full sanitization suite is required:** Fingerprints originate from `_extract_classifier_signal(result)[:80]` which concatenates raw stderr, stdout, and embedded JSON-derived text (`recovery_gate.py:2105-2132`). This is untrusted input from prior tool execution — every attack class that `sanitize_for_prompt` defends against (confusable-character keyword bypass, verdict-marker injection, instruction-like patterns, zero-width hiding) is reachable through this path. A weaker sanitizer would leave known prompt-shaping payload classes admissible in the `learning_context` injection surface. **Why not import `sanitize_for_prompt` from `tools.runners.shared_agent_utils`:** That module is a runner bootstrap with import-time side effects — it clears `CLAUDECODE` from the environment (`shared_agent_utils.py:27`) and monkey-patches the Claude SDK message parser (`shared_agent_utils.py:32-46`). Importing it into `recovery_gate.py` would violate the file's declared import constraint ("only stdlib + executor_common") and inject runner-side bootstrapping behavior into the executor-side recovery gate. The local helper replicates the full security-relevant measure set while avoiding this coupling. The confusable-character translation table is a simple `str.maketrans` dict (stdlib-only, defined inline).
- Returns sanitized formatted string or empty string

### (b) Wire `run_review.py` prompt construction

- **Decouple from `--no-memory`:** Learning context injection uses a new `self.use_learning` attribute (default `True`), NOT `self.use_memory`. Rationale: learning store patterns are pipeline-recovery knowledge (accumulated failure/fix data from `recovery_gate.py`), not session memory (agent memory context from `agent_memory.py`). The `--no-memory` flag was designed to suppress session memory bleed, not to block pipeline-recovery context. Gating learning injection behind `--no-memory` would leave the Phase B SDK review surface cold: `phase_b_executor.py:1253-1259` hard-codes `--no-memory` in all review invocations, so learning context would never reach SDK agents during the automated pipeline.
- **New `--no-learning` flag:** `run_review.py` accepts `--no-learning` CLI argument (sets `use_learning=False`). When set, learning context is not computed or injected. This provides explicit opt-out without overloading `--no-memory` semantics.
- **Independence:** `--no-memory` suppresses `memory_context` and `pattern_context` (from `agent_memory.py`). `--no-learning` suppresses `learning_context` (from `recovery_gate.py`). They are independent flags controlling orthogonal concerns.
- **Report-packet exclusion (DEFECT FIX):** When `build_report_packet_context(self.files)` returns non-empty (all review targets are `reports/*.md`), learning context injection is suppressed regardless of `use_learning`. Rationale: `REPORT-PACKET REVIEW MODE` (`run_review.py:295-309`) constrains agents to verify claims against cited evidence only and not roam beyond the packet. Historical learning-store snippets are pipeline-recovery knowledge accumulated from prior tool execution — they are not packet-cited evidence and would contaminate the bounded evidence-only review discipline. This limits warming to its intended surfaces: implementation/code-review prompts (SDK agent code reviews and Phase B implementer), where pipeline-recovery context is actionable. The guard is checked at prompt-construction time: if the report-packet context is active, `load_relevant_learnings()` is not called and `## Learning Context` is not emitted.
- When `self.use_learning` is True AND not in report-packet review mode: call `load_relevant_learnings(agent_name, self.files, active_repo_root)` and inject result as `## Learning Context` section in prompt (parallel to `memory_context`)
- Separate 4000-character budget (does not share with `memory_context` cap; sanitization is handled inside `load_relevant_learnings()` via `_sanitize_learning_output()`, not at this call site)
- **Phase B SDK review surface (addresses `phase_b_executor.py:1253-1259`):** The existing Phase B review invocation passes `--no-memory` but NOT `--no-learning`. Because learning context is independent of `--no-memory`, SDK review agents receive warming with no modification to the Phase B review command. This closes the gap identified in the review: the pipeline's SDK-agent review surface is warm.

### (c) Wire `phase_b_executor.py` to `phase_b_implementer.py`

- `phase_b_executor.py`: compute `learning_context = load_relevant_learnings("implementer", plan_declared_files, repo_root)` once
- Pass to `build_implementation_prompt(learning_context=learning_context)` at all call sites
- `phase_b_implementer.py`: add `learning_context: str = ""` kwarg to `build_implementation_prompt()`, inject as `## Learning Context` section

### (d) Tests

**`test_recovery_gate.py`** — `load_relevant_learnings` unit tests:
- Returns formatted string with promoted patterns
- Agent-specific filtering: `implementer` gets only `test_failure`/`git_staging_conflict`/etc. entries; `verifier` gets all entries (unfiltered); `grounding` gets `test_failure`/`needs_phase_b`/`unknown_error` entries
- Unknown agent name defaults to unfiltered (all entries)
- 4000-character cap enforced (`len(result) <= 4000`)
- Empty store/file returns empty string (graceful degradation)
- **Sanitization:** Output is sanitized — inject a fingerprint containing prompt-injection markers (e.g., triple backticks, instruction-like patterns, zero-width characters, Greek/Cyrillic confusable characters, `VERDICT:`/`OVERALL_VERDICT:` markers) and verify they are neutralized in the returned string. Specifically: `_extract_classifier_signal`-derived fingerprints contain raw stderr/stdout, so test that `load_relevant_learnings()` strips/escapes these via the local `_sanitize_learning_output()` helper. Verify confusable-character translation prevents keyword-redaction bypass (e.g., Greek Α in "ignore previous" is normalized to Latin A before redaction fires)

**`test_run_review.py`** — SDK agent warming wiring:
- `run_review.py` injects learning_context into prompt for all 9 agents when `use_learning=True` (default) and targets are code files (not report packets)
- **`--no-learning` opt-out:** When `use_learning=False` (via `--no-learning`), learning_context is NOT computed or injected (verify `load_relevant_learnings` is not called and prompt does not contain `## Learning Context` section)
- **`--no-memory` independence (Phase B SDK review proof):** When `use_memory=False` (via `--no-memory`) but `use_learning=True` (default) and targets are code files, learning_context IS still injected. This directly tests the decoupling added in work item (b) and proves the Phase B SDK review surface is warm: `phase_b_executor.py:1253-1259` passes `--no-memory` but not `--no-learning`, so SDK agents must still receive warming.
- **Report-packet exclusion:** When `use_learning=True` (default) but all review targets are `reports/*.md` packets (`build_report_packet_context()` returns non-empty), learning_context is NOT injected. Verify `load_relevant_learnings` is not called and prompt does not contain `## Learning Context` section. This proves that `REPORT-PACKET REVIEW MODE` evidence-only discipline is not contaminated by historical pipeline-recovery snippets.

**`test_phase_b_executor.py`** — Phase B surface proof (addresses existing `TestBuildImplementationPrompt` at lines 70-125):
- `build_implementation_prompt(plan, ..., learning_context="## Learning Context\n...")` includes the `## Learning Context` section in output
- `build_implementation_prompt(plan, ..., learning_context="")` does NOT include a `## Learning Context` section (empty string = no injection)
- `phase_b_executor.py` passes `learning_context` kwarg to every `build_implementation_prompt()` call site (verify all call sites receive the kwarg)

## 3. Constraints

- NO changes to Tier 1-3 recovery logic
- NO changes to runtime (`mu/host/`)
- NO changes to `agent_memory.py` (warming ownership stays in `recovery_gate.py`)
- Existing `get_pattern_context()` in `agent_memory.py` is NOT modified
- `learned_patterns.json` read via existing `_load_learning_store()` only -- no new file readers
- `recovery_gate.py` import constraint preserved: only stdlib + executor_common. NO imports from `tools.runners.*` — sanitization is handled by a local stdlib-only `_sanitize_learning_output()` helper, not by importing `sanitize_for_prompt` from runner-side modules
- **Deferred: domain-level taxonomy extension.** Adding agent-domain categories (security, complexity, structural correctness) to `FailureClass` is OUT OF SCOPE for this enabler wave. The design doc (`PipelineRecovery.v0.md:280`) aspirationally requires domain-level filtering ("adversary gets security-related learnings, expert gets complexity learnings"), but the current enum models only pipeline-recovery conditions. Until the taxonomy is extended in a future wave, non-pipeline agents (adversary, verifier, expert, structural-proof, translator, visualizer, advisor) receive unfiltered pipeline-recovery context. This is an explicit scope-down, not a contract satisfaction claim

## 4. Stop Conditions

1. `load_relevant_learnings()` returns agent-filtered, sanitized content from JSON store (promoted patterns with pipeline-subset filtering for implementer/grounding/fuzzer; unfiltered for all others — explicit scope-down from design doc's domain-level filtering aspiration, deferred pending `FailureClass` taxonomy extension) and FIXED entries from learning.md (session-captured fixes, included unfiltered — no `failure_class` metadata available)
2. `load_relevant_learnings()` output is sanitized via local `_sanitize_learning_output()` before returning — fingerprints containing prompt-injection markers (instruction-like patterns, verdict markers, confusable characters, zero-width characters, triple backticks) are neutralized using the complete security-relevant measure set from `sanitize_for_prompt` (no runner-side imports — local stdlib-only reimplementation)
3. `run_review.py` injects learning_context into all 9 agent prompts when `use_learning=True` (default) and targets are code files (not report packets)
4. `run_review.py` does NOT inject learning_context when `use_learning=False` (`--no-learning` opt-out)
5. `run_review.py` DOES inject learning_context when `use_memory=False` but `use_learning=True` and targets are code files — `--no-memory` does not suppress learning context (Phase B SDK review surface proof: `phase_b_executor.py:1253-1259` passes `--no-memory` but not `--no-learning`)
6. `run_review.py` does NOT inject learning_context when all targets are `reports/*.md` packets, regardless of `use_learning` — `REPORT-PACKET REVIEW MODE` evidence-only discipline is preserved (historical learning-store snippets are not packet-cited evidence)
7. `phase_b_implementer.py` receives and renders learning_context from `phase_b_executor.py`
8. All new tests pass: `pytest mu/tests/tools/test_recovery_gate.py mu/tests/tools/test_run_review.py mu/tests/tools/test_phase_b_executor.py -v`
9. Phase B surface proof: `test_phase_b_executor.py` proves `learning_context` kwarg propagation through all `build_implementation_prompt()` call sites
10. Existing tests in touched files still pass: `pytest mu/tests/tools/ -v --timeout=30`

Note: `tools/pre-push-fast` is executor/closeout-owned (see `phase_b_implementer.py:100-103`). It runs during `commit_executor.py` Step 11, not during Phase B implementation. The Phase B implementer MUST NOT run it.

## 5. Acceptance Criteria

1. `load_relevant_learnings("adversary", [], repo_root)` returns all pipeline-recovery patterns (unfiltered) — **scope-down acknowledged:** design doc (`PipelineRecovery.v0.md:280`) aspirationally requires domain-level filtering but current `FailureClass` taxonomy has no domain-level categories; this wave delivers pipeline-recovery warming only for non-pipeline agents. Domain-level filtering is deferred pending taxonomy extension (see Section 3 constraint)
2. `load_relevant_learnings("implementer", [], repo_root)` returns only `test_failure`, `git_staging_conflict`, `process_timeout`, `implementer_stale`, `needs_phase_b`, `mixed_staging` entries (pipeline-subset filtering)
3. Output is capped at 4000 characters (`len(result) <= 4000`) regardless of store size — cap enforced by `_sanitize_learning_output(max_len=4000)` post-sanitization
4. Empty `learned_patterns.json` and missing `.claude/rules/learning.md` both degrade to empty string without error
5. **Sanitization:** `load_relevant_learnings()` output passes through local `_sanitize_learning_output()` (stdlib-only, defined in `recovery_gate.py`) — fingerprints containing triple backticks, instruction-like patterns, zero-width characters, confusable Greek/Cyrillic characters, or verdict-marker patterns (`VERDICT:`, `OVERALL_VERDICT:`) are neutralized before returning to any caller. The local helper replicates the complete security-relevant measure set from `sanitize_for_prompt` (confusable translation, verdict redaction, instruction redaction, zero-width stripping, backtick escaping, NFKC normalization, truncation). No import from `tools.runners.shared_agent_utils` is introduced.
6. `run_review.py` prompt includes `## Learning Context` section when `use_learning=True` (default), learning store has content, and targets are code files (not report packets)
7. **`--no-learning` opt-out:** `run_review.py` does NOT inject `## Learning Context` when `use_learning=False` (via `--no-learning`) — verified by test that `load_relevant_learnings` is not called and prompt omits the section
8. **Report-packet exclusion:** `run_review.py` does NOT inject `## Learning Context` when all review targets are `reports/*.md` packets, regardless of `use_learning`. `REPORT-PACKET REVIEW MODE` (`run_review.py:295-309`) constrains agents to verify claims against cited evidence only — historical learning-store snippets are not packet-cited evidence and would contaminate this bounded review discipline. Verified by test that `load_relevant_learnings` is not called and prompt omits `## Learning Context` when `build_report_packet_context()` returns non-empty
9. **`--no-memory` independence (Phase B SDK review surface):** `run_review.py` DOES inject `## Learning Context` when `use_memory=False` (via `--no-memory`) but `use_learning=True` (default) and targets are code files. This proves the Phase B SDK review path (`phase_b_executor.py:1253-1259`, which hard-codes `--no-memory`) delivers warming to SDK agents. (Phase B reviews target code files, not report packets, so the report-packet exclusion does not affect this surface.)
10. `phase_b_implementer.py` prompt includes `## Learning Context` section when `learning_context` kwarg is non-empty
11. Existing `get_pattern_context()` behavior in `agent_memory.py` is unchanged
12. No new file readers introduced -- all reads go through existing `_load_learning_store()` and `_load_session_fixed_entries()`
13. `build_implementation_prompt(learning_context=...)` kwarg is tested in `test_phase_b_executor.py`: non-empty string produces `## Learning Context` section, empty string produces no section
14. All `build_implementation_prompt()` call sites in `phase_b_executor.py` pass `learning_context` kwarg (verified by dedicated test)

## 6. Grounding / Authorization

- **Parent task:** `[PIPELINE-RECOVERY]` (TASKS.md line 177-185). IN PROGRESS, founder-authorized.
- **Authorization:** TASKS.md line 184: Phase 5 learning store code baseline landed (PR #751). Integration gaps remain: "no `.claude/rules/learning.md` cross-pollination, no subagent warming."
- **Predecessor:** Item A (cross-pollination) landed via PR #768 (`6eb429a5`). This wave covers the injection-surface portion of Item B (subagent warming): `load_relevant_learnings()` function + all prompt injection paths (SDK review + implementer) + pipeline-subset filtering for implementer/grounding/fuzzer. **Not delivered in this wave:** domain-level relevance filtering for 7 non-pipeline agents (design doc `PipelineRecovery.v0.md:280`) — the `FailureClass` taxonomy lacks domain-level categories (security, complexity, structural correctness). A follow-up wave is required to extend the taxonomy and satisfy the design doc's full relevance contract.
- **Governing packet:** This file (`reports/control_plane/learning-store-warming-2026-04-12_2026-04-13.md`). Supersedes untracked predecessor `reports/control_plane/learning_store_warming_2026-04-12.md` (Item B design draft, same scope, never committed).
- **Design doc:** `mu/docs/agents/PipelineRecovery.v0.md` (subagent learning injection).
- **Wave class:** L4_ENABLER
- **target_gate_id:** G8

## Request from Post-Merge Supervisor

Item A (cross-pollination, PR #768) merged. Item B (subagent warming) is the remaining integration gap cited in TASKS.md line 184. This wave delivers the learning store injection surface (all prompt paths warmed, pipeline-subset filtering for implementer/grounding/fuzzer). It does NOT complete the design doc's full Item B contract: domain-level relevance filtering for 7 non-pipeline agents (adversary, verifier, expert, structural-proof, translator, visualizer, advisor) remains undelivered pending `FailureClass` taxonomy extension (see Section 3 constraint).