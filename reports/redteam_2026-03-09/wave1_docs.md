# RCX Review Report (in progress)

**Date:** 2026-03-09 15:47
**Files:** mu/docs/, roadmap/, STATUS.md, TASKS.md, ROADMAP.md, CLAUDE.md
**Depth:** quick
**Status:** Running — latest: verifier → REQUEST_CHANGES

## Results So Far

| Agent | Verdict | Status |
|-------|---------|--------|
| structural-proof (GATE) | UNPROVEN | ⚠️ Non-compliant |
| expert | COULD_SIMPLIFY | ⚠️ Non-compliant |
| adversary (GATE) | NEEDS_HARDENING | ⚠️ Non-compliant |
| verifier (GATE) | REQUEST_CHANGES | ❌ Fail |

## Detailed Reports

### Structural-Proof

**⚠️ Compliance Error:** 2 incomplete finding blocks;   - Finding 'STATUS.md integrity line claim...' missing: LINES, CODE;   - Finding 'TASKS.md trigger references "c...' missing: LINES, CODE

```
### CHECKED
- **Seed files location**: All seeds present in `mu/` (canonical location). 19 seed files found across substrate/closures/programs/utilities/bridge subdirectories.
- **Seed census**: `mu/tests/structural/test_seed_counts.py` `EXPECTED_COUNTS` is the authoritative machine-verified source. Sums to **19 seeds, 162 projections**.
- **Agent runners**: 14 runner files verified in `mu/tools/runners/` (verifier, adversary, advisor, expert, skeptic, translator, visualizer, structural-proof, grounding, fuzzer, deep-analysis, interactive, review, ci-review).
- **`terminal_classify.v1.json`**: Exists in `mu/utilities/` — previous memory flag resolved (NOT a regression).
- **`bootstrap_structural.v1.json`**: Exists in `mu/bridge/` — previous memory flag resolved (NOT a regression).
- **61/6 projection claim**: Verified as accurate for the 6-seed subset it references (kernel.v1:7 + match.v2:8 + subst.v2:12 + recurrence.v1:9 + exhaustion.v1:13 + hemispheres.v1:12 = 61 ✓).
- **L3 Seed Categories table in STATUS.md**: Matches actual MU_SEEDS structure.
- **TASKS.md VECTOR P2 reference**: Not dangling — checkpoint/resume contract referenced at line 645 is real.
- **CLAUDE.md `seeds/*.json` legacy location**: No broken references found; all seed paths resolve to `mu/`.

---

### NOT_CHECKED
- **JS parity claims**: Cannot verify without running `node mu/host/js/eval_step.js` — CI-only.
- **docstring behavioral accuracy** in `mu/docs/`: Would require full test suite execution.
- **`tests/l4_gates/` evidence_command tests**: Existence and integrity not verified in this pass.
- **`@host_builtin` marker completeness**: `isinstance` audit in boundary drain loops not checked.

---

### FINDING 1: Stale Seed Count in STATUS.md

```
FINDING: STATUS.md integrity line claims 17 seeds and 143 projections — both wrong
FILE: /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/STATUS.md
LINES: ~772
CODE: "[x] Seed integrity: 17 seeds, 143 projection IDs, 0 intra-seed collisions"
VERIFIED: Yes
```

Authoritative source (`test_seed_counts.py`) shows **19 seeds, 162 projections**. The checklist item is stale by 2 seeds and 19 projection IDs.

---

### FINDING 2: Stale Re-Evaluation Trigger in TASKS.md

```
FINDING: TASKS.md trigger references "current 17 files" — corpus is actually 19
FILE: /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/TASKS.md
LINES: ~656
CODE: "Re-evaluation trigger unchanged: projection count >50 or seed corpus doubles from current 17 files."
VERIFIED: Yes
```

Should read 19, not 17.

---

### Verdict
`VERDICT: UNPROVEN`

Two structural baseline claims (seed count = 17, projection IDs = 143) are contradicted by the authoritative machine-verified source in `test_seed_counts.py` (19 seeds, 162 projections). All downstream claims that reference these numbers (integrity checks, re-evaluation thresholds) inherit the staleness. No claims are `IMPOSSIBLE_AS_CLAIMED` — the fixes are straightforward doc corrections — but the current state is **unproven** until STATUS.md line ~772 and TASKS.md line ~656 are updated to reflect the actual corpus.

---

**Ready to fix these two stale count references?** Both are doc-only corrections (STATUS.md + TASKS.md). I can patch them now and send through bridge review before asking for commit approval.
```

### Expert

**⚠️ Compliance Error:** 1 incomplete finding blocks;   - Finding 'ROADMAP.md duplicates and lags...' missing: CODE

```
Here is the Expert Lens complexity review:

---

# Expert Lens: Complexity & Minimalism Audit

**Scope:** `mu/docs/`, `roadmap/`, `STATUS.md`, `TASKS.md`, `ROADMAP.md`, `CLAUDE.md`

---

### CHECKED

- **TASKS.md line budget:** 743 lines total. Ra (Resolved/Merged) section = 494 lines (66%). Active work sections (NEXT/VECTOR/SINK) = 137 lines combined. Governance preamble = 95 lines. Previous finding (403/631 = 64%) confirmed as persisting at same ratio — Ra grew proportionally with total file.
- **TASKS.md tracker sync note density:** Individual tracker sync notes (e.g., W11-EVIDENCE-WALKER) run 80-90 lines each with full evidence matrices. This is intentional L4 compliance archival, not accidental bloat. Evidence chains are audit-grade and gate-required.
- **TASKS.md SINK Heartbeat Tracker:** Minor duplication — promotion state (e.g., "D005 authorized for NEXT") appears in both SINK tracker table and NEXT section text. Not critical; ~5 lines overlap.
- **STATUS.md structure (816 lines):** Well-sectioned (phase definition, L1-L4 levels, debt status, agent enforcement, testing tiers). No dead sections. Debt explanation appears twice (lines ~317 and ~365) but with distinct context (general floor vs. CP-S1A history). Intentional layering, not duplication.
- **CLAUDE.md structure (505 lines):** Clean architecture — behavioral protocol, session onboarding, agent guide, workflow, test classification, L4 contract summary. No stale file references detected (all paths verified as existing). Cross-file with STATUS.md testing tiers is appropriate (prescriptive vs. descriptive).
- **ROADMAP.md (41 lines):** Minimal pointer doc. However, lines 6-21 duplicate the reading order already in `roadmap/MANIFEST.md` (and ROADMAP.md lists 11 items vs MANIFEST.md's 13 — ROADMAP.md is **out of date**).

FINDING: ROADMAP.md duplicates and lags behind roadmap/MANIFEST.md
FILE: /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/ROADMAP.md
LINES: 6-21
CODE: Reading order list (11 items) duplicates roadmap/MANIFEST.md (13 items, more current)
VERIFIED: Yes

- **mu/docs/ (55 files across agents/, audit/, cli/, core/, execution/, schemas/):** No dead files detected. All files referenced in test-enforced manifest (`tests/docs/test_manifest_discoverability.py` prevents orphaning). Thematic separation is appropriate: DeepStep has 3 files (spec/guards/tutorial) — intentional, not duplication. Agent docs have 5 files with distinct purposes (bridge, runbook, rig, guardrails, template).
- **roadmap/ (8 files):** `L4ExecutionContract.v1.md` is superseded but explicitly marked as historical reference in MANIFEST.md — not dead, intentionally archived. No duplication between roadmap/ (draft designs) and mu/docs/core/ (approved specs).
- **Cross-file duplication audit:** L4 policy appears in CLAUDE.md (summary), TASKS.md (SINK tracker), and roadmap/ (canonical spec) — intentional summary-vs-spec pattern. Testing tiers in both CLAUDE.md and STATUS.md serve different purposes. Agent commands in CLAUDE.md are an index pointing to canonical runbooks. No problematic duplication.
- **Memory regression check (STATUS.md seed count claims):** Previous finding about "61/6 contradicts own L3 table (127/15)" — reviewed L3 table and seed list in both STATUS.md and TASKS.md North Star #13. Seed lists now appear consistent (12 named seeds in both locations).

### NOT_CHECKED

- **Content accuracy of individual mu/docs/ files** (55 files; only verified existence, not internal accuracy vs. current code)
- **Whether Ra tracker sync notes are individually accurate** (verified format and structure, not factual claims within evidence matrices)
- **Whether CLAUDE.md L3 seed list matches `test_seed_counts.py::EXPECTED_COUNTS`** at current HEAD (referenced in memory as previous verifier finding)
- **mu/docs/ files referenced from code comments** (only checked references FROM governance docs, not TO governance docs)
- **Archive directory structure** (not scoped for this review)

### Verdict

VERDICT: COULD_SIMPLIFY

**Rationale:** The documentation architecture is fundamentally sound — canonical sources, indexed pointers, test-enforced manifests. However, two concrete simplification opportunities exist:

1. **ROADMAP.md should be collapsed to a 5-line pointer** to `roadmap/MANIFEST.md` instead of maintaining a stale duplicate of the reading order. The current 41-line file duplicates content that's better maintained in MANIFEST.md, and it's already fallen out of sync (11 items vs. 13).

2. **TASKS.md Ra section (494 lines, 66%)** is structurally appropriate for L4 compliance but makes the active task sections hard to find. A lightweight improvement: add a table-of-contents header with line anchors so readers can jump past the archive to NEXT/VECTOR/SINK. No extraction needed — just navigation.

Neither finding rises to OVER_ENGINEERED. The system is disciplined and well-layered, with one stale pointer and one navigation friction point.
```

### Adversary

**⚠️ Compliance Error:** 4 incomplete finding blocks;   - Finding '`--admin` merge contradicts CI...' missing: CODE;   - Finding 'Active bridge config uses undo...' missing: CODE

```
I can see that `terminal_classify.v1` is indeed absent from the L3 Seed Categories table (lines 97-104) in STATUS.md, confirming the memory finding. CLAUDE.md line 64 claims it as one of the 12 required seeds, but STATUS.md's L3 table doesn't list it.

Now I have enough data to compile the full adversary report.

---

# RCX Adversary Review Report — Documentation & Governance Layer

**Scope:** `mu/docs/`, `roadmap/`, `STATUS.md`, `TASKS.md`, `ROADMAP.md`, `CLAUDE.md`
**Date:** 2026-03-09
**Agent:** Adversary (Red-Team Security)

---

### CHECKED

- **GraphQL thread-resolve mutation (CLAUDE.md lines 168-189):** Documented pattern allows programmatic resolution of ALL review threads without addressing findings. Combined with `--admin` flag on line 188, this constitutes a complete code-review governance bypass. Any repository admin can: (1) resolve all threads via GraphQL, (2) merge with `--admin`. No audit trail, no safeguard.

- **`--admin` policy conflict (CLAUDE.md line 188 vs CI_POLICY.md line 33):** CLAUDE.md documents `gh pr merge --admin` as standard workflow. CI_POLICY.md states "Branch protection cannot be bypassed, including by admins." These are in direct contradiction. The `--admin` flag bypasses branch protection on GitHub when used by admins — CI_POLICY.md's claim is aspirational, not enforceable.

- **Environment variable security gate bypass (pre-commit-doc-check):** `RCX_SKIP_AGENT_CHECK=1` and `RCX_SKIP_ADVERSARY_CHECK=1` suppress security review sections. These are documented in the hook header (lines 15-18) but have no authentication, no logging, and no policy restricting their use. Any local process can suppress adversary review silently.

- **Bridge `--dangerously-skip-permissions` flag (.agent_bus/bridge_config.json line 5):** Active bridge config includes undocumented `--dangerously-skip-permissions` flag for Claude subprocess. Not present in the example config (`tools/agents/bridge_config.example.json`). No validation of allowed flags in `bridge_adapters.py` — any flag can be injected into the agent command.

- **Bridge protocol has no authentication (AgentBridgeProtocol.v0.md):** Agent identity is determined solely by config file command. No signing, no HMAC, no verification that the subprocess is actually Claude/Codex. Config injection → prompt exfiltration or response forgery.

- **Git hooks bypassable (pre-push-fast line 78):** Hook explicitly documents bypass: "To bypass (not recommended): git push --no-verify". This is a git design constraint, but no server-side enforcement closes the gap.

- **STATUS.md L3 Seed Categories table (lines 97-104) omits `terminal_classify.v1`:** CLAUDE.md line 64 lists 12 seeds including `terminal_classify.v1.json` as required for both substrates. STATUS.md's L3 table lists only 14 seeds across 5 categories — `terminal_classify.v1` is absent. This is a documentation-reality gap where the seed exists but the canonical status table doesn't track it, creating a blind spot for parity verification.

- **STATUS.md "6 listed seeds" claim (line ~81):** Line 81 states "The SAME projections (all 4 seed files)" referencing only kernel, match, subst, recurrence. This contradicts the 12-seed L3 requirement in CLAUDE.md and the 14-seed L3 categories table in STATUS.md itself. Multiple conflicting seed counts create confusion about what requires parity.

- **TASKS.md Ra section bloat:** Ra (Resolved/Merged) now consumes 495 of 743 lines (67%). Not a security vulnerability, but the signal-to-noise ratio degrades the ability to review active work items — a governance smell.

- **TASKS.md NEXT section is all completed:** All 4 items in NEXT are struck-through with COMPLETE status. NOW section is empty. This means there are no active work items, which is either correct (project complete) or a governance drift (tasks exist but aren't tracked).

---

### NOT_CHECKED

- **Runtime code paths** (rcx_pi/selfhost/, mu/host/js/) — out of scope for this doc-focused review. Adversary attack families (type confusion, injection, smuggling) require code-level review.
- **Actual CI enforcement** — whether GitHub Actions workflows enforce the policies documented in CI_POLICY.md. Requires inspecting `.github/workflows/` and GitHub repo settings.
- **Bridge SQLite bus integrity** — whether the bus can be corrupted or injected into at the data layer.
- **Agent memory tampering** — whether `.agent_memory/findings.json` can be modified to suppress findings or forge cooldown timestamps.
- **Seed file integrity** — whether JSON seed files can be tampered with to inject malicious projections (requires code-level review of seed loading and validation).
- **`metabolize_cycle.v1.json`** — exists in `mu/programs/` but not listed in any canonical seed list. Unknown whether it requires parity. Not verified.

---

### Findings

**FINDING: GraphQL review-thread auto-resolve enables governance bypass**
FILE: /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/CLAUDE.md
LINES: 168-189
CODE:
```bash
gh api graphql -f query='mutation {
  resolveReviewThread(input: {threadId: "<THREAD_ID>"}) {
    thread { isResolved }
  }
}'
# 3. Then merge normally
gh pr merge <PR_NUM> --merge --delete-branch --admin
```
VERIFIED: Yes — documented in CLAUDE.md, no guard against abuse

**FINDING: `--admin` merge contradicts CI_POLICY.md branch protection claim**
FILE: /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/CLAUDE.md
LINES: 188
CODE: `gh pr merge <PR_NUM> --merge --delete-branch --admin`
VERIFIED: Yes — CI_POLICY.md line 33 states "Branch protection cannot be bypassed, including by admins"

**FINDING: Security review suppressible via undocumented-risk env vars**
FILE: /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/mu/tools/hooks/pre-commit-doc-check
LINES: 15-18, 153, 178
CODE:
```bash
#   RCX_SKIP_AGENT_CHECK=1      -> suppress agent reminder
#   RCX_SKIP_ADVERSARY_CHECK=1  -> suppress adversary reminder/run
```
VERIFIED: Yes — hook confirms non-blocking, suppressible by env var

**FINDING: Active bridge config uses undocumented `--dangerously-skip-permissions`**
FILE: /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/.agent_bus/bridge_config.json
LINES: 5
CODE: `"cmd": ["claude", "--print", "--dangerously-skip-permissions", "--model", "opus"]`
VERIFIED: Yes — absent from example config and protocol docs

**FINDING: `terminal_classify.v1` missing from STATUS.md L3 Seed Categories table**
FILE: /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/STATUS.md
LINES: 97-104
CODE: (table lists 14 seeds across 5 categories; terminal_classify.v1 absent despite being in CLAUDE.md line 64 as required)
VERIFIED: Yes — grep for "terminal_classify" in STATUS.md returns zero matches

**FINDING: STATUS.md line 81 claims "all 4 seed files" but 12+ seeds require parity**
FILE: /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/STATUS.md
LINES: 81
CODE: `- The SAME projections (all 4 seed files) run on Python AND JavaScript`
VERIFIED: Yes — contradicts own L3 categories table (14 seeds) and CLAUDE.md (12 seeds)

---

### Verdict

VERDICT: NEEDS_HARDENING

**Rationale:** No direct runtime exploit was demonstrated (runtime code was out of scope for this doc review). However, the governance layer has concrete, exploitable bypass mechanisms:

1. **GraphQL + `--admin` = complete review bypass** — trivially executable by any admin
2. **Env var gate suppression** — no authentication, logging, or policy guard
3. **Bridge config injection** — undocumented dangerous flag, no config validation
4. **Policy contradictions** — CLAUDE.md and CI_POLICY.md disagree on admin bypass

These are not theoretical — they are documented workflows that a contributor could follow today to bypass security review without detection. The governance intent is strong (CLAUDE.md rules 1-8 are rigorous), but the technical enforcement has gaps that undermine those intentions.

**Priority hardening recommendations:**
1. Add explicit warnings to the GraphQL thread-resolve section: "Resolving without addressing = governance violation"
2. Reconcile `--admin` usage between CLAUDE.md and CI_POLICY.md
3. Add `terminal_classify.v1` to STATUS.md L3 Seed Categories table
4. Fix STATUS.md line 81 "all 4 seed files" → reference actual count
5. Document `--dangerously-skip-permissions` in AgentBridgeProtocol.v0.md or remove from active config
6. Consider making adversary check blocking (not just reminder) in pre-commit hook
```

### Verifier

```
I now have all the evidence needed. Here is my full verifier report:

---

## RCX Verifier Report — mu/docs/, roadmap/, STATUS.md, TASKS.md, ROADMAP.md, CLAUDE.md

---

### CHECKED

- **STATUS.md Phase/Level claims**: Phase 8c, L1 DONE, L2 FULL, L3 COMPLETE, L4 SINK — all internally consistent with TASKS.md structure.
- **Kernel projection count**: STATUS.md claims `kernel.v1.json` has 7 projections. Confirmed: exactly 7 projection IDs in `mu/substrate/kernel.v1.json`. Test confirms via `test_seed_counts.py::EXPECTED_COUNTS`.
- **Seed projection counts (all seeds)**: All 19 seed files verified against `EXPECTED_COUNTS` in `mu/tests/structural/test_seed_counts.py`. Every actual count matches the test expectation. No drift.
- **JS debt count**: STATUS.md claims "16 total (9 iteration + 4 recursion + 3 builtin)" per `constants.js` canonical header. Verified: header lists exactly 9 + 4 + 3 = 16 distinct host operations. Explanation for grep discrepancy (19) is accurate.
- **bootstrap_structural.v1.json existence**: File exists at `mu/bridge/`, 5 projections, listed in L3 table as Bridge. Confirmed.
- **terminal_classify.v1.json existence**: File exists at `mu/utilities/`, 7 projections. Confirmed.
- **All CLAUDE.md Key Files (lines 441–452)**: Every referenced file/directory exists: STATUS.md, TASKS.md, mu/docs/core/, mu/docs/agents/AgentRig.v0.md, mu/host/python/rcx_pi/selfhost/, mu/host/js/eval_step.js, mu/substrate/, mu/closures/, mu/programs/.
- **NorthStarSemantics.v0.md**: Exists at `mu/docs/core/`, has DOC_STATUS header.
- **roadmap/MANIFEST.md reading order**: Exists and consistent with references in ROADMAP.md and CLAUDE.md.
- **mu/docs/ DOC_STATUS headers**: All 32 files in `mu/docs/core/` have DOC_STATUS headers. No missing headers detected.
- **tests/docs/ test files**: 13 real test files with actual assertions (test_doc_contracts.py, test_doc_freshness.py, test_doc_governance.py, etc.). NOT test theater — comprehensive governance tests. Previous memory finding ("test theater") is a FALSE POSITIVE (regression cleared).
- **TASKS.md structure**: Ra=511 lines (68.8%), NEXT=9 items, VECTOR=26 items, SINK=22 items. No dangling VECTOR P2 reference in S1. No stale "in NEXT" qualifier in S1 dependencies. Previous memory findings are cleared.
- **ROADMAP.md**: Clean sequencing view. Correctly defers to STATUS.md and TASKS.md for state. No operational state duplication.
- **CLAUDE.md `seeds/*.json` legacy location**: Previous memory finding about "nonexistent seeds/*.json legacy location" — NO match found in current CLAUDE.md. Regression cleared.
- **JS parity of terminal_classify.v1**: Confirmed loaded by JS via `seed_loader.js` (line 77), `terminal_classification.js` (line 60). Both substrates load it.

---

### FINDINGS

**FINDING 1: STATUS.md L3 Seed Categories table is stale — missing 5 seeds, wrong JS parity claim for Utilities**

FINDING: STATUS.md L3 Seed Categories table omits 5 seeds and falsely marks Utilities as "Python-only"
FILE: /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/STATUS.md
LINES: 97-104
CODE:
```
| **Utilities** | classify.v1, eval.v1 | Python-only | Optional - helper algorithms |
| **Programs** | rcx_engine.v1, hemispheres.v1, metabolization.v1, paxos_demo.v1 | rcx_engine + hemispheres + metabolization: ✅ | ... |
```
VERIFIED: Yes

**Evidence:**
- `terminal_classify.v1` is LOADED BY JS (`mu/host/js/core/seed_loader.js` line 77, `terminal_classification.js` line 60) but is absent from the table entirely.
- `metabolize_cycle.v1` is LOADED BY JS (`mu/host/js/core/seed_loader.js` line 82, `mu/host/js/cli/main.js` line 227) but absent from the Programs row.
- `evidence_walker.v1` is LOADED BY JS (`mu/host/js/core/seed_loader.js` line 83) but absent from the Utilities row.
- `match.v1` and `subst.v1` exist in JS (`seed_loader.js` lines 66, 68) but absent from the Substrate row.
- The "Python-only" claim for the Utilities row is **FALSE** — both `terminal_classify.v1` and `evidence_walker.v1` are JS-loaded.
- `test_seed_counts.py` (the canonical source of truth, lines 26-30) lists all 19 seeds correctly. The STATUS.md table only lists 14.

**Fix direction:** Update the L3 Seed Categories table to include all 19 seeds from `test_seed_counts.py::EXPECTED_COUNTS`, and correct the JS parity column for Utilities.

---

**FINDING 2: CLAUDE.md L3 seed list (line 64) is incomplete — missing metabolize_cycle.v1 and evidence_walker.v1**

FINDING: CLAUDE.md lists 12 seeds as loaded by both substrates but omits 2 JS-loaded seeds
FILE: /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/CLAUDE.md
LINES: 64
CODE:
```
- Both substrates load the SAME seed files: `kernel.v1.json`, `match.v2.json`, `subst.v2.json`, `recurrence.v1.json`, `recurrence.v2.json`, `exhaustion.v1.json`, `fix.v1.json`, `bootstrap_structural.v1.json`, `hemispheres.v1.json`, `rcx_engine.v1.json`, `metabolization.v1.json`, `terminal_classify.v1.json`
```
VERIFIED: Yes

**Evidence:**
- `metabolize_cycle.v1.json` (15 projections) is loaded by JS (`seed_loader.js` line 82, `cli/main.js` line 227) but not listed.
- `evidence_walker.v1.json` (4 projections) is loaded by JS (`seed_loader.js` line 83) but not listed.
- The same omission appears in TASKS.md North Star #13 (line 23), which lists the same 12 seeds.

**Fix direction:** Add `metabolize_cycle.v1.json` and `evidence_walker.v1.json` to the seed list in CLAUDE.md line 64 and TASKS.md North Star #13.

---

### NOT_CHECKED

- **Actual JS parity execution** (whether JS produces identical output to Python for all seeds) — requires `pytest tests/parity/test_js_parity_automated.py` to confirm.
- **Pre-commit hook runtime behavior** (doc checks, adversary gate) — not executed, only structure verified.
- **Runtime code paths** in `rcx_pi/selfhost/` for host smuggling, isinstance without @host_builtin, or Python == on Mu values — these are code-level attacks outside the doc review scope.
- **Indicator artifact provenance** in `reports/l4_wave_indicators/` — not audited (no wave in progress).
- **Agent memory findings for STATUS.md advisor claims** ("Seed count claim 61/6 contradicts L3 table 127/15") — these refer to historical STATUS.md state and cannot be verified against current file without running the full audit pipeline.
- **TASKS.md Ra bloat** — Ra is 68.8% of the file (511 of 743 lines). This is a maintenance concern but not a North Star violation.

---

### Verdict

VERDICT: REQUEST_CHANGES

**Rationale:** Two concrete doc drift violations are demonstrated:
1. STATUS.md L3 Seed Categories table is missing 5 seeds and makes a false "Python-only" claim for Utilities (terminal_classify.v1 and evidence_walker.v1 are both JS-loaded).
2. CLAUDE.md and TASKS.md seed lists omit metabolize_cycle.v1 and evidence_walker.v1 from the "both substrates" list.

Both are falsifiable claims with evidence from `seed_loader.js` and `test_seed_counts.py`. The test infrastructure correctly tracks all 19 seeds, but the documentation has drifted. Fixes are straightforward table/list updates.
```
