# RCX Task List (Canonical)

This file is the single source of truth for authorized work.
If a task is not listed here, it is NOT to be implemented.

---

## North Star (Keep This True)

1. RCX VM is not a "runner". It is a substrate where **structure is the primitive**.
2. "Code = data" means execution is graph/mu transformation, not host-language semantics.
3. **Stall → Fix → Trace → Closure** is the native engine loop; everything else must serve it.
4. Closures/gates must be **explicit, deterministic, and measurable** (fixtures + replay).
5. Emergence must be attributable to RCX dynamics, not "Python did it".
6. Host languages are scaffolding only; their assumptions must not leak into semantics.
7. Buckets (r_null / r_inf / r_a / lobes / sink) are **native routing states**, not metaphors.
8. Seeds must be minimal (void/empty) and growth must be structurally justified.
9. Determinism is a hard invariant: same seed + rules ⇒ same trace/fixtures.
10. A "program" is a pressure vessel: seed + allowable gates + thresholds + observation outputs.
11. Enginenews-like specs are target workloads to prove: "does ω/closure actually emerge?"
12. Every task must answer: "Does this reduce host smuggling and increase native emergence?"
13. **L3 Parity: Python and JavaScript must run identical projections with identical semantics.**
    - Same seeds: kernel.v1, match.v2, subst.v2, recurrence.v1, recurrence.v2, exhaustion.v1, fix.v1, hemispheres.v1, rcx_engine.v1, metabolization.v1, bootstrap_structural.v1, terminal_classify.v1, metabolize_cycle.v1 (projection counts verified by `mu/tests/structural/test_seed_counts.py::EXPECTED_COUNTS`)
    - Same bootstrap primitives: eval_step, max_steps, stack_guard, projection_loader (mu_equal DEMOTED — Level 1 Content-Addressed Mu)
    - Any change to Python projection behavior MUST be mirrored in JS
    - Any new seed MUST be loaded and tested in BOTH substrates
14. **Seeds must declare their execution layer.** Every seed is either:
    - **BOOTSTRAP**: Runs via eval_seed.step() only (Python/JS substrate provides non-linear pattern support)
    - **META-CIRCULAR**: Runs via step_kernel_mu (kernel.v1 + match.v2 + subst.v2)
    - If a seed claims META-CIRCULAR, tests MUST verify it through step_kernel_mu
    - Non-linear pattern seeds become META-CIRCULAR only when bridge-backed structural runtime is default
    - Current BOOTSTRAP seeds: eval.v1 (uses [] arrays, requires bootstrap match/substitute)
    - Current META-CIRCULAR seeds: kernel.v1, match.v2, subst.v2, recurrence.v1, exhaustion.v1, classify.v1
15. **True self-hosting is the path.** The goal is structural computation without host semantics:
    - **L1 (Algorithmic)**: match/subst algorithms as Mu projections ✓ DONE
    - **L2 (Operational)**: kernel loop as Mu projections ✓ DONE (with bootstrap primitive acceptance)
    - **L3 (Substrate Portability)**: same projections run on Python AND JavaScript ✓ DONE
    - **L4 (True Self-Hosting)**: eliminate bootstrap primitives OR make them substrate-independent
    - Programs must run accurately and structurally, without host semantics (except irreducible bootstrap)
    - Tests must verify the CLAIMED execution path, not just correctness
    - If tests pass via bootstrap but fail via meta-circular kernel, that's a real bug (not theater)

---

## Governance (Non-Negotiable)

- Do not add new subsystems, execution models, or architectures without explicit approval.
- Do not create "new tests" to bypass a failing test; fix the failing test or the code.
- Do not leave broken files/tests behind and add replacements.
- Minimize file creation. Prefer editing existing files.
- v1 replay semantics are frozen. Any new observability must be v2 and gated.
- **L3 Parity Rule**: Changes to `mu/host/python/rcx_pi/selfhost/` (or via symlink `rcx_pi/selfhost/`) or `mu/` MUST be mirrored in `mu/host/js/eval_step.js`.
  - Run `node mu/host/js/eval_step.js` to verify all JS tests pass
  - Run `./tools/checks/check_js_debt.sh` to verify JS debt markers match Python
  - Run `./tools/checks/linters/contraband_js.sh` to verify no forbidden patterns (determinism, purity)
  - Run `./tools/checks/linters/ast_police_js.sh` to catch JS patterns that bypass grep
  - Run `./tools/checks/check_test_theater_js.sh` to catch vacuous JS assertions
  - Run `./tools/checks/linters/seed_police.sh` to verify seed integrity and no host leakage
  - New seeds must be loaded in both Python and JavaScript
  - Parity vectors must pass on both substrates before merge
- **Pre-commit doc review**: Before committing changes to `rcx_pi/` or `mu/`:
  1. Read relevant docs in `mu/docs/` (e.g., EVAL_SEED.v0.md, DeepStep.v0.md)
  2. Update docs if implementation differs from spec
  3. Update TASKS.md status if completing/progressing items
  4. Verify JS parity if projection behavior changed
- **Agent runbook**: Agent usage follows `mu/docs/agents/AgentRunbook.v0.md` (trigger map, gate rules, and evidence requirements)
- **Roadmap rule**: `ROADMAP.md` and docs in `roadmap/` define SEQUENCE and DESIGN only.
  - Current state lives in STATUS.md; authorization lives in TASKS.md
  - Gate completion updates TASKS.md (Ra/NEXT/VECTOR), not roadmap docs
  - Draft specs live in `roadmap/`; approved specs migrate to `mu/docs/core/`
  - See `roadmap/MANIFEST.md` for reading order and linking rules

## Collaboration Protocol (Default Working Mode)

- **VECTOR mode (design/creation)**: Explore ontology-to-runtime mappings, propose alternatives, and identify missing mechanisms. No implementation begins in VECTOR.
- **NEXT mode (execution/verification)**: Implement bounded, testable slices only. Mirror Python/JS semantics and preserve deterministic behavior.
- **Falsifiability gate**: Every new design claim must map to a measurable runtime behavior and at least one concrete test criterion.
- **Cross-model continuity**: Inputs from Codex, Claude, or Gemini are design references, not authority. Canonical authority remains `STATUS.md` + `TASKS.md`.
- **Promotion discipline**: Creative proposals must be explicitly promoted (`VECTOR -> NEXT`) before code changes.

---

## Promotion Criteria (Non-Negotiable)

- **SINK → VECTOR**: Item must have a clear semantic question to answer. A design doc must be written before any implementation. Promotion must be explicit and documented in this file.
- **VECTOR → NEXT**: Design doc must be complete and reviewed. Semantics must be locked. Implementation scope must be bounded and testable. Observability must precede mechanics.
- Promotion is never implicit. Moving an item between sections requires updating this file with rationale.
- **PR rule**: Any PR that implements a VECTOR/SINK item without an explicit promotion note in this file must be rejected.
- No implementation work may begin on VECTOR items. VECTOR is design-only.
- No SINK item may advance without answering: "What semantic question does this resolve?"

**Terminology Lock:** `sink` (lowercase) = runtime hemisphere bucket (e.g., `r_sink` in projection routing). `SINK` (uppercase) = governance task lane (this section, parked work items). `r_a` = runtime accumulator bucket. `Ra` = resolved-work section (below). These are distinct concepts; never conflate them.

---

## Ra (Resolved / Merged)

- Tracker sync note (2026-04-07, anti-drift-enforcement-2026-04-07): **ANTI-DRIFT-ENFORCEMENT — 26 binary patches, hook hardening, STATUS.md consolidation.** Class: MAINTENANCE. target_gate_id: G8. no_op_proof: no runtime files changed. no_op_proof: no runtime files changed, tooling only (.claude/skills/preflight/SKILL.md). defer_reason_code: TOOLING_FOLLOWUP. evidence_command: wc -l STATUS.md. primary_blocker_class: INTEGRATION. primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION. indicator_artifact_ref: reports/l4_wave_indicators/anti-drift-enforcement-2026-04-07.json. indicator_collection_command: python3 tools/metrics/collect_l4_wave_indicators.py --wave-id anti-drift-enforcement-2026-04-07 --output reports/l4_wave_indicators/anti-drift-enforcement-2026-04-07.json. bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. boot0_track_id: V1. boot0_progress_state: HOLD. FOUNDER_OVERRIDE:anti-drift-enforcement-2026-04-07 (founder authorized consecutive MAINTENANCE — anti-drift enforcement is prerequisite for all future structural work, cannot defer). unblocks_wave_id: wave-meta-bridge-bounded-review-fix. unblocks_runtime_blocker: INV_STRUCTURAL_FORWARD_MOTION
- Tracker sync note (2026-04-07, persona-tasks-cleanup-2026-04-07): **PERSONA-TASKS-CLEANUP — engineering identity persona, TASKS.md compaction, settings upgrade.** Class: MAINTENANCE. target_gate_id: G8. no_op_proof: no runtime files changed, tooling/docs only (TASKS.md, .claude/rules, .claude/skills, .claude/settings.local.json, archive/). defer_reason_code: TOOLING_FOLLOWUP. evidence_command: `wc -l TASKS.md`. evidence_delta: (1) TASKS.md compacted 774→305 lines (60% reduction, 236 tracker notes archived). (2) Engineering identity persona deployed across 6 injection layers (.claude/rules/persona.md). (3) Preflight cron updated with identity self-audit. (4) settings.local.json hook updated with identity reinforcement. (5) April tracker notes archived to archive/tasks_ra_april_2026.md. FOUNDER_OVERRIDE:persona-tasks-cleanup-2026-04-07 (founder authorized MAINTENANCE for persona upgrade + TASKS.md compaction — required for protocol compliance and session rigor). primary_blocker_class: INTEGRATION. primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION. indicator_artifact_ref: reports/l4_wave_indicators/persona-tasks-cleanup-2026-04-07.json. indicator_collection_command: python3 tools/metrics/collect_l4_wave_indicators.py --wave-id persona-tasks-cleanup-2026-04-07 --output reports/l4_wave_indicators/persona-tasks-cleanup-2026-04-07.json. bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. boot0_track_id: V1. boot0_progress_state: HOLD.
- Tracker sync note (2026-04-07, preflight-hardening-2026-04-07): **PREFLIGHT-HARDENING — 20-step preflight with config backup, binary deep-read, 28-patch verification, auto-update disable.** Class: L4_ENABLER. target_gate_id: G8. evidence_command: `grep -c '^[0-9]' .claude/skills/preflight/SKILL.md`. evidence_delta: (1) Preflight expanded 17→20 steps. (2) Step 10: config backup + write-protect (CLAUDE.md, MEMORY.md, .claude/rules/). (3) Step 17: CC version detection + backup comparison. (4) Step 18: binary deep-read for contradictions on version change. (5) Step 19: 28-patch verification (added P27 anti-redteam, P28 anti-verification from CX4). (6) Step 20: auto-update disable check. progress_proof_before: preflight had 17 steps, no config backup, no binary deep-read, 19-patch verification. progress_proof_after: preflight has 20 steps, config backup+write-protect, binary deep-read on version change, 28-patch verification, auto-update disable. FOUNDER_OVERRIDE:preflight-hardening-2026-04-07 (founder authorized MAINTENANCE for preflight hardening). primary_blocker_class: INTEGRATION. primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION. indicator_artifact_ref: reports/l4_wave_indicators/preflight-hardening-2026-04-07.json. indicator_collection_command: python3 tools/metrics/collect_l4_wave_indicators.py --wave-id preflight-hardening-2026-04-07 --output reports/l4_wave_indicators/preflight-hardening-2026-04-07.json. bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. boot0_track_id: V1. boot0_progress_state: HOLD. 
- Tracker sync note (2026-04-08, meta-bridge-taskid-path-safety-2026-04-03): **META-BRIDGE-BOUNDED-REVIEW-FIX — task-ID path safety, startup-flow suppression, zero-match envelope, lock_plan regex, stale-timeout alignment.** Class: L4_ENABLER. target_gate_id: G8. evidence_command: PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_meta_bridge_supervisor.py mu/tests/tools/test_executor_dispatch.py -q --tb=short. evidence_delta: (1) Task IDs with slashes no longer crash meta-bridge file creation. (2) Pre-commit meta-review no longer reruns founder guard/attest startup flows. (3) Zero-match probe commands produce valid envelopes. (4) lock_plan() Status regex matches any Status text, not just one specific phrase. (5) META_STALE_TIMEOUT_S aligned to 300s matching bridge review timeout. progress_proof_before: meta-bridge supervisor crashes on slash task IDs, reruns startup flows, aborts on clean probes. progress_proof_after: all three problems fixed with regression tests, plus lock_plan and stale-timeout hardening. primary_blocker_class: INTEGRATION. primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION. indicator_artifact_ref: reports/l4_wave_indicators/meta-bridge-taskid-path-safety-2026-04-03.json. indicator_collection_command: python3 tools/metrics/collect_l4_wave_indicators.py --wave-id meta-bridge-taskid-path-safety-2026-04-03 --output reports/l4_wave_indicators/meta-bridge-taskid-path-safety-2026-04-03.json. bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. boot0_track_id: V1. boot0_progress_state: HOLD. FOUNDER_OVERRIDE:meta-bridge-taskid-path-safety-2026-04-03 (founder authorized expanded scope — lock_plan regex fix and META_STALE_TIMEOUT_S alignment bundled with bounded-review-fix as both are supervisor-hardening, not separate structural work).
Items here are implemented and verified under current invariants. Changes require explicit promotion through VECTOR and new tests. Completed NOW/NEXT items are archived here.

- **[META-BRIDGE-S1] CLOSED** (2026-03-28). Pre-commit meta-bridge supervisor implemented and proven. PRs #641-#644 (impl), #653 (routing fix). Seeded-package verification complete. All follow-on items spawned as separate tasks and completed: [PRE-COMMIT-SUPERVISOR-STANDING], [META-BRIDGE-S2], [EXECUTOR-SURFACES].

- **[META-BRIDGE-S2] CLOSED** (2026-03-28). Post-merge routing supervisor implemented and merged (PR #657). Routing-only deliberation authority. Proven through 9 PRs in pipeline sprint.

- **[EXECUTOR-SURFACES] CLOSED** (2026-03-28). All 6 slices complete (PRs #659-#661). 4 executors (dialectic, Phase A, Phase B, commit) + dispatcher + config. Rollout steps 5+6 combined. Commit pipeline automation plan Phase A locked (19 bridge rounds). Phase B proven through [PIPELINE-TEST-RUN].

- **[PRE-COMMIT-SUPERVISOR-STANDING] CLOSED** (2026-03-28). Pre-commit supervisor LIVE as standing gate. Wired into commit_executor.py step 5. 10 validation gates. Per-invocation UUID receipt. Hardened (path traversal, decision allowlist, Gate 10 field bugs, envelope validation). Proven through 9 PRs.

- **[PIPELINE-TEST-RUN] CLOSED** (2026-03-28). Full 15-step commit pipeline proven end-to-end. PR #673 completed the boring-path proof (post-merge routed ROUTE_PHASE_B, Phase B executor ran implementer + agents + bridge convergence, commit executor completed all 15 steps through merge). PRs #674-#681 landed follow-on hardening (stale watchdog, finding history, compliance hook, routing retry, handoff builder, supervisor scope bounding, bot review auto-refresh, pipeline monitor). 9 PRs total through full mechanical pipeline. Tracked packet: `reports/control_plane/pipeline_test_run_2026-03-25.md`.

- **[COMMIT-EXECUTOR-E2E] CLOSED** (2026-03-28). 15-step commit executor proven mechanically by [PIPELINE-TEST-RUN] evidence: 9 PRs (#673-#681) completed the full pipeline (ensure_feature_branch through ensure_review_clear_and_merge). Both COMMIT_GO and COMMIT_GO_HOLD_PUSH paths exercised. Tracked packet: `reports/control_plane/commit_pipeline_automation_plan_2026-03-22.md`.


*Last compacted: 2026-04-07. Pre-March notes: `archive/tasks_ra_pre_march_2026.md`. March notes: `archive/tasks_ra_march_2026.md`. April notes: `archive/tasks_ra_april_2026.md`.*

> **Archive:** 148 pre-March tracker notes archived to [`archive/tasks_ra_pre_march_2026.md`](archive/tasks_ra_pre_march_2026.md).
> 209 March tracker notes archived to [`archive/tasks_ra_march_2026.md`](archive/tasks_ra_march_2026.md).
> 27 April tracker notes archived to [`archive/tasks_ra_april_2026.md`](archive/tasks_ra_april_2026.md).

---

## Boundary Question (Answered)

What is the smallest, host-independent execution primitive that RCX must possess
such that a structural program can cause new structure to emerge only via
Stall → Fix → Trace → Closure, and in no other way?

**Answer:** The Structural Reduction Loop (MATCH → REDUCE/STALL → TRACE → NORMAL_FORM).
See `archive/docs/MinimalNativeExecutionPrimitive.v0.md` for invariants and non-goals.

---

## NOW (normally empty; founder-directed exceptions may pin an active Codex queue)

- ~~**[NOW-CODEX-REDTEAM]**~~ **CLEARED** (2026-03-28, founder-authorized).
  Control-surface lane complete: meta-bridge S1+S2, executor surfaces, pre-commit supervisor, pipeline test run, commit executor E2E — all closed to Ra.
  Follow-on structural queue unparked as [NEXT-CODEX-POST-REDTEAM].
  Original packet: `reports/control_plane/meta_bridge_rollout_2026-03-20.md`.

---

## NEXT (short, bounded follow-ups)

- **[ANTI-DRIFT-ENFORCEMENT]** **NEXT** (2026-04-07, founder-authorized).
  Anti-drift enforcement: 26 binary patches removing Anthropic system prompt contradictions, hook hardening (cron evidence gate, test-result claim gate, PostCompact comprehensive reinject, block-protected-branch false-positive fix), persona RCX production quality discipline, preflight 17-step auto-repatch + backup comparison, STATUS.md consolidation (849→489 lines), hook consolidation to tracked settings.json, dream protection for 9 memory files.
  **Lane:** control-surface (enforcement hardening).
  FOUNDER_OVERRIDE:anti-drift-enforcement-2026-04-07 (founder authorized consecutive MAINTENANCE for anti-drift enforcement — prerequisite for all future structural work, cannot defer). unblocks_wave_id: wave-meta-bridge-bounded-review-fix. unblocks_runtime_blocker: INV_STRUCTURAL_FORWARD_MOTION.

- **[META-BRIDGE-BOUNDED-REVIEW-FIX]** **NEXT** (2026-04-01, founder-authorized).
  Keep `FOUNDER_SESSION_BOOTSTRAP.md` reading required for Codex reviewers, but stop the pre-commit meta-review from rerunning founder guard/attest startup flows or self-aborting on clean zero-match probe commands before emitting an envelope.
  **Tracked packet:** `reports/control_plane/meta_bridge_taskid_path_safety_2026-04-03.md`
  **Lane:** control-surface (supervisor hardening).
  *Immediate next wave — has tracked packet.*

- **[PIPELINE-RECOVERY]** **IN PROGRESS** (2026-03-31, founder-authorized).
  Pipeline failure recovery system — tiered auto-fix/retry/diagnose/escalate.
  **Design:** `mu/docs/agents/PipelineRecovery.v0.md`
  **File:** `mu/tools/executors/recovery_gate.py`
  ~~**Phase 1:** Classifier + Tier 1 auto-fix~~ **Landed** (PR #704).
  ~~**Phase 2:** Wired into dispatcher retry loop + hardened~~ **Landed** (PR #705).
  ~~**Phase 3:** Tier 2 auto-retry + Tier 3 recovery loop function~~ **Landed** (9/9 items via [RECOVERY-TIER3-WIRING], closed 2026-04-06).
  **Remaining:** (5) Learning store.
  **Lane:** control-surface (pipeline hardening).

- **[DEFERRED-CONSOLIDATION]** **IN PROGRESS** (2026-03-31).
  Consolidate 6 overlapping deferred files. Wave 1A (9 critical/high) ~~**Landed**~~ (PR #703). Wave 1B (18 medium/low) queued.
  - **[DEFERRED-CONSOLIDATION/pr711-landed-marker-2026-04-04]** **NEXT** (2026-04-04, founder-authorized).
    Mark the stale merged tracker sync note as landed so the global push gate stops falsely blocking unrelated routed waves.
  **Plans:** `reports/control_plane/wave1b_pipeline_cleanup_2026-03-31.md`
  **Lane:** control-surface (deferred cleanup).

- **[NEXT-CODEX-POST-REDTEAM]** **UNPARKED** (2026-03-28, founder-authorized).
  Structural follow-on queue: `reports/control_plane/post_redteam_structural_queue_2026-03-20.md`.
  **Sequence:** Phase A → Phase B → Phase C → Phase D.
  **Current phase:** Phase A — structural gap sweep.
  **Lane:** structural (post-control-surface).

- **[PARALLEL-PIPELINE]** **QUEUED** (2026-03-31, founder-authorized).
  Enable parallel pipelines across git worktrees with agent teams.
  **Depends on:** [PIPELINE-RECOVERY] Phase 1 (landed), agent bus namespacing.
  **Work items:** (1) Agent bus namespacing — `--bus-dir` flag on executors, per-worktree `.agent_bus-{id}/` (~1 wave). (2) Per-worktree dashboard ports + tmux session names from config (trivial). (3) Recovery gate Tier 2 — auto-retry on transient kills (already designed). (4) Agent teams integration — teammates auto-create worktrees with namespaced buses.
  **Solves:** scope creep from dirty worktrees, bridge "state changed" stale retries, shared lock contention, dashboard port collisions.
  **Lane:** control-surface (pipeline scaling).

The completed items below are retained for test-contract cross-reference only — they are NOT active authorization.

- ~~**[S1-SCHED]**~~ **COMPLETE** (2026-03-15, moved to Ra). L4 production reduction — all 33 projections via Stage0 VM (PR #606).
- ~~**Hemisphere Metabolization Contract**~~ **CLOSED** (2026-02-20, moved to Ra). PROMOTED FROM VECTOR P1. Metabolization projections implemented, E1-E5 all MET.
- ~~**Boot1 Recursive Loop Contract**~~ **CLOSED** (2026-02-19, moved to Ra). Boot1 recursive is default, E1-E5 all MET.
- ~~**D005 Production Pilot (Staged Bootstrap)**~~ **CLOSED** (2026-03-01, moved to Ra). Stage 0 micro-kernel integrated with pilot flag (PR #452).
- ~~**GAP-10-LOOP**~~ **CLOSED** (2026-02-14, moved to Ra). Structural iteration control — transitional trampoline via _config carry-through.

**Gate Snapshot (Canonical mirror of STATUS.md):**
- Gate 3: COMPLETE (2026-02-07)
- Gate 4: COMPLETE (2026-02-07 structural cutover)
- Gate 5: COMPLETE (2026-02-09 meta-circular parity verified)
  - 56 exit criteria tests: 9 gate5 parity + 17 execution path + 30 JS parity
  - Structural execution default; bootstrap explicit fallback only
  - Cross-substrate parity intact (Python + JS, all L3 seed projections — see test_seed_counts.py)
  - `run_algorithm_meta_circular()` defaults to `step_kernel_mu(..., kernel_mode="bridge", validation_mode="algorithm_runtime")` on production path.

Current Recurrence Layer: META_CIRCULAR
Current Exhaustion Layer: META_CIRCULAR


## VECTOR (design-only; semantics locked, no implementation allowed)


**Active designs (priority-ordered):**
- ~~**[P1] L4 G8 Production Decision Path (D004→D005)**~~ — **PROMOTED TO NEXT** (2026-03-01, d008-founder-go-render). D008 GO rendered (founder, 2026-03-01; supersedes prior DEFER). All 5 promotion criteria satisfied: (1) D004/D008 founder verdict rendered = GO, (2) D005 pilot spec bounded by D004 constraints (≤100 LOC/substrate), (3) D004 stop conditions enumerated (§4), (4) L3 parity path defined (D004 §3), (5) This explicit VECTOR → NEXT promotion. D005 authorized for execution under D004 constraints.
- **[P2]** Checkpoint/Resume Contract (bounded continuation semantics) — Explicit pause/resume semantics when engine or algorithm limits are hit. **Opened** (2026-02-14, Round 16E). **Founder decision D2=DEFER** (2026-02-16): not promoted; remains in VECTOR for future consideration. **Invariants**: (1) Limit hit is explicit (no silent truncation), (2) Hash verifies state integrity; hash alone is not resumable state, (3) Resume token carries full continuation state (or validated pointer), state_hash, seed/version checksums, and budget metadata, (4) Resume path preserves Python/JS parity, (5) Resume path reuses existing validation/security guards, (6) No bootstrap primitive count increase without explicit approval. **Promotion criteria (all required for VECTOR → NEXT):** (1) Contract doc drafted and approved, (2) Canonical token schema defined, (3) Cross-substrate parity test plan defined, (4) Security review complete, (5) Explicit VECTOR → NEXT promotion in this file with rationale.
- **[P3]** Content-Addressed Mu (`roadmap/ContentAddressedMu.md`) - Every Mu value carries a content hash; equality becomes O(1). **Levels 0-2 IMPLEMENTED** (L0: boundary hashing, L1: mu_equal eliminated 5→4, L2: frozen hashes — state dropped from _seen, ~77% memory savings). **Level 3 (Trie) DEFERRED** — analysis shows 5x slower for production traces (<50 steps), break-even at ~100 steps. Revisit if traces routinely exceed 100 steps.
- **[P4]** Projection Indexing - Preprocess projections into structural trie/decision-tree for O(log N) matching instead of O(N) linear scan. Index is Mu data (structural). **Promotion criteria:** Profile real workloads first; if projection matching is >50% of runtime, promote to NEXT. **Profiling plan (2026-03-02):** Measure `_match_inner`/`match` as fraction of `run_engine_pipeline` end-to-end time on canonical cycling workload (A↔B, 2 projections, 10 steps, 20 engine iterations, 100 algorithm iterations).
  - Python: `PYTHONHASHSEED=0 python3 - <<'PY'` with `cProfile` harness: `from rcx_pi.selfhost.step_mu import run_engine_pipeline; run_engine_pipeline([{"id":"c.l","pattern":{"state":"A"},"body":{"state":"B"}},{"id":"c.l","pattern":{"state":"B"},"body":{"state":"A"}}], {"state":"A"}, max_steps=10, max_engine_iterations=20, max_algorithm_iterations=100, use_boot1_recursive=False)` — inspect `pstats.Stats(pr).sort_stats("cumtime").print_stats(40)`.
  - JS: `node --cpu-prof mu/host/js/eval_step.js --json-api '{"action":"run_engine_pipeline","projections":[{"id":"c.l","pattern":{"state":"A"},"body":{"state":"B"}},{"id":"c.l","pattern":{"state":"B"},"body":{"state":"A"}}],"input":{"state":"A"},"maxSteps":10,"maxEngineIterations":20,"maxAlgorithmIterations":100}'` — load `.cpuprofile` in Chrome DevTools or `speedscope`. **Note:** `eval_step.js` runs self-tests before `--json-api` dispatch; isolate the `runEnginePipeline` call subtree when reading the profile (ignore `runSelfTests` startup).
  - **Go/no-go rule:** GO P4 only if projection matching/selection hotspot is >50% of end-to-end runtime on measured workloads. If ≤50%, explicitly defer P4, record measured percentages, and set re-evaluation trigger (re-measure when projection count exceeds 50 or new seed files double current corpus).
  - **Measurement results (2026-03-02) — P4 DEFERRED with measured evidence:**
    - Python canonical (2 projs, cycling A↔B): `_match_inner` cumtime = 2.376s / 4.696s = **50.6%**; tottime (self-only) = 0.886s = **18.9%**. 94.6% of 272k match attempts are NO_MATCH (failures P4 could skip). P4-addressable savings estimate: **47.8%** (below threshold).
    - Python secondary (8 projs, 7 inputs): `_match_inner` cumtime = 2.676s / 5.900s = **45.4%** (below threshold).
    - JS canonical (engine subtree only, self-tests excluded): `match()` = 143.2ms / 362.2ms = **39.5%** (below threshold).
    - Dominant non-matching overhead: `is_mu`/`assert_mu` validation (Python 36-41%), `muHashCached` stall detection (JS 16.2%).
    - **Decision: DEFER.** Cumtime-based 50.6% is borderline but inflated by inclusive counting of operations any implementation needs (isinstance, dict.keys). The P4-addressable fraction (failed match elimination) is 47.8%. Secondary workload and JS are clearly below 50%. Re-evaluation trigger unchanged: projection count >50 or seed corpus doubles from current 19 files.
- **[P5]** Debt Categories v0 (`mu/docs/core/DebtCategories.v0.md`) - Scaffolding vs semantic debt distinction
- ~~**[P6]** Typed Numeric Envelopes~~ — **DECIDED** (2026-03-01, founder). **Decision: Option A (NO strict lexical parity) with containment discipline.** Accept substrate-model difference as intentional. Seeds remain integer-only. Policy lock tests enforced. Re-evaluation triggers: first real workload requiring mixed numeric non-linear matching, or observed closure/routing divergence. Design packet: `mu/docs/core/TypedNumericEnvelopes.v0.md`. PR #455 (design packet), decision recorded same session.
- ~~**[P7] Host Semantics Reduction — 4 Bootstrap Primitives.**~~ **PROMOTED TO NEXT** (2026-03-13, founder directive). See NEXT section for concrete scope.
- ~~**[P8] Native Agent Subagents Migration.**~~ **COMPLETE** (2026-03-11, native-agent-migration + agent-optimization waves). **Decision: Two-system architecture** — native Claude Code subagents (`.claude/agents/*.md`) for ad-hoc interactive use, SDK orchestrator (`run_review.py`) retained for batch/rigorous mode. 9 native agents created, sync script (`sync_native_agents.sh`) regenerates from source-of-truth prompts. Full replacement deferred — SDK orchestrator provides phase ordering, retry logic, and rigorous mode skeptic challenge that native subagents lack.
- ~~**[P9] TASKS.md Compaction.**~~ **COMPLETE** (2026-03-13, Wave 19). Option A executed: 148 pre-March tracker notes archived to `archive/tasks_ra_pre_march_2026.md`. TASKS.md compacted 807→397 lines (51% reduction). A11 gate test updated to check archive. No enforcer or test dependency on inline content broken.

**EngineNew gap contracts** (locked by `tests/structural/test_engine_cycle_mapping.py::TestGapRegistry`):
- ~~GAP-04-FIX~~ — **CLOSED** (2026-02-13, Round 15I). E1–E5 complete. `fix.v1.json` (6 projections) + `rcx_engine.v1.json` (10 projections, 3 fix-dispatch). 19 invariant tests, 4 cross-substrate parity tests. EngineNew 9/10 structural.
- ~~GAP-10-LOOP~~ — **CLOSED** (2026-02-14, Round 16E). E1–E4 complete. Trampoline makes loop-back decision structural (11 projections). 10/10 EngineNew steps structural. Boot1 Recursive Loop Contract remains open as parallel VECTOR item for L4 path.

**Reference:**
- Corpus Status Registry (`mu/docs/corpus_registry.csv`) - 18-artifact classification with taxonomy labels, confidence scores, and evidence refs. Ontology-to-runtime mapping reference for VECTOR design work.

**Promoted to NEXT:**
- ~~Mu Hemispheres v0~~ (`roadmap/MuHemispheresDesign.md`) - **PROMOTED TO NEXT** (2026-02-09, Gate 5 blocker resolved)
- ~~Boot1 Recursive Loop Contract~~ (`mu/docs/core/Boot1LoopContract.v0.md`) - **PROMOTED TO NEXT** (2026-02-16, founder D1=YES). Shadow-merge scope: no default flip, no trampoline removal. All 6 promotion criteria satisfied. P1-P3 resolved.
- ~~Hemisphere Metabolization Contract~~ (`roadmap/MuHemispheresDesign.md` § Metabolization) - **PROMOTED TO NEXT** (2026-02-19). All 5 promotion criteria satisfied. Boot1 complete + D008 re-evaluation trigger met. Execution checklist: `mu/docs/core/HemisphereExecutionChecklist.v0.md`.
- ~~L4 G8 Production Decision Path (D004→D005)~~ - **PROMOTED TO NEXT** (2026-03-01, d008-founder-go-render). D008 GO (founder). All 5 promotion criteria satisfied. D005 pilot authorized under D004 constraints.

**Completed (moved to Ra):**
- ~~Operator Exhaustion v0~~ (`mu/docs/core/OperatorExhaustion.v0.md`) - **MOVED TO Ra** (IMPLEMENTED 2026-02-02)
  - Step 6 complete: 11 projections in `mu/closures/exhaustion.v1.json`
  - 27 tests (17 parity + 10 fuzzer), cross-substrate parity verified

**Historical promotion (completed):**
- Meta-Circular Kernel v0 (`mu/docs/core/MetaCircularKernel.v0.md`) - promoted 2026-01-27, implemented and archived in `Ra`

**Completed designs (now in Ra):**
- RCX Kernel v0 (`mu/docs/core/RCXKernel.v0.md`)
- Structural Purity v0 (`mu/docs/core/StructuralPurity.v0.md`)
- Self-Hosting v0 (`mu/docs/core/SelfHosting.v0.md`)
- EVAL_SEED v0 (`mu/docs/core/EVAL_SEED.v0.md`)
- EngineNews Structural v0 (`mu/docs/core/EngineNewsStructural.v0.md`) - Step 5 closure detection
- Operator Exhaustion v0 (`mu/docs/core/OperatorExhaustion.v0.md`) - Step 6 operator freeze
- Second Independent Encounter (`mu/docs/execution/IndependentEncounter.v0.md`)
- Enginenews Spec Mapping (`mu/docs/execution/EnginenewsSpecMapping.v0.md`)
- Closure Evidence Events (`mu/docs/execution/ClosureEvidence.v0.md`)
- Rule-as-Motif (`mu/docs/execution/RuleAsMotif.v0.md`)

**Archived (superseded):**
- Bytecode VM v0/v1 → `archive/docs/bytecode/`

---

## SINK (ideas parked; may not advance without explicit promotion decision)

**Items (priority-ordered):**
- **[S1]** L4 Full Self-Hosting Rewrite — long-horizon goal: eliminate all 4 bootstrap primitives entirely. **G8 PASS (classification gate, caveated, 2026-03-03).** All four primitives classified REDUCIBLE_WITH executable evidence (D001 analytical + D002-D003 + D005-D010 executable). G1-G7 PASS. G8 PASS closes primitive classification evidence, not L4 completion. L4 remains blocked by stop conditions #3 (host for-loop) and #4 (L3-to-L4 gap). No full bootstrap-primitive elimination claims — bounded production reduction has occurred (S1-B/S1-C: VM cutover active, 33 projections on Stage0 VM) but all 4 primitives (eval_step, max_steps, stack_guard, projection_loader) remain in production. Productionization of full elimination requires separate gates (see L4ExitChecklist.v0.md productionization gate lock). See `mu/docs/core/L4ExitChecklist.v0.md` for gate criteria and `mu/docs/core/L4DecisionCard.v0.md` for G8-ADJ verdict. **→ Production reduction phase promoted to NEXT as [S1-SCHED] (2026-03-11, founder directive).**
- **[S2]** Projection caching optimization (post-Phase 8) - cache normalized projections for repeated use; use content-based hash, NOT id(). From withdrawn KernelSeedRealignment.v0.md.
- **[S3]** Multi-value/concurrent execution
- **[S4]** Performance-first optimizations
- **[S5]** D010 Binary Seed Format (TLV) — convert JSON seeds to compact binary. **FOUNDER_DEFERRED (2026-03-11).** Not blocking L4 meta-circularity (BP-5: orthogonal to structural execution path). Open design questions: int-range policy, NaN/Inf round-trip, migration strategy, checksum policy. Revisit when performance becomes a bottleneck.
- ~~Full VM bootstrap / meta-circular execution~~ → Promoted to VECTOR #14 (RCX Kernel v0)

**Conjecture Parking (NOT ACTIVE):**
- **Hypothesis:** Non-Euclidean / topological RCX manifold geometry; structural linear algebra overlays on Mu projections.
- **Non-goal:** No embedding, gradient, or continuous-space semantics in core runtime. Outside math concepts are mechanism inspiration only; RCX ontology remains primary.
- **Status:** PARKED. No implementation, no design doc, no active exploration.
- **Re-evaluation trigger:** Explicit founder GO + gate-mapped evidence command (must target a specific L4 gate).
- **Promotion rule:** Must map to one specific gate AND one bounded experiment (single wave, ≤1 week). No rabbit-hole expansion without bounded evidence plan.

**L4 Heartbeat Tracker (next 3 waves):**

| wave_id | target_gate | artifact_or_noop_proof | owner | decision_deadline | status |
|---------|-------------|------------------------|-------|-------------------|--------|
| wave6 | G8 | D006 H1 fuel threading experiment | RCX Core | 2026-02-26 | DONE — H1 PARTIALLY CONFIRMED (D006). `tests/research/test_d006_h1_fuel_threading.py` |
| wave7 | G8 | D007 H3 negative control experiment | RCX Core | 2026-03-05 | DONE — H3 FALSIFIED (expected, D007). `tests/research/test_d007_h3_negative_control.py` |
| wave8 | G8 | D008 evidence closure + founder decision packet | Founder | 2026-03-12 | CLOSED — D008 GO rendered (founder, 2026-03-01; supersedes DEFER). D005 authorized for NEXT. |
| d009 | G8 | D009 H4 stack_guard depth threading experiment | RCX Core | 2026-03-09 | DONE — H4 PARTIALLY CONFIRMED (D009). `tests/research/test_d009_h4_depth_threading.py` |
| d010 | G8 | D010 H5 projection_loader binary format experiment | RCX Core | 2026-03-09 | DONE — H5 PARTIALLY CONFIRMED (D010). `mu/tests/research/test_d010_h5_projection_loader_binary.py` |
| g8-adj | G8 | G8 adjudication closeout — PASS (classification gate, caveated) | Founder | 2026-03-03 | DONE — G8 PASS (classification gate, caveated, 2026-03-03). 4/4 executable evidence. |
| rt3 | G5 | RT3 anti-theater residual-gap closure + canonicalization | RCX Core | 2026-03-03 | DONE — RT3 checker hardening merged (PR #465). 18 tests, 5 bypass vectors closed. Docs canonicalized. |

**Post-D008 Operating Mode:** D008 GO rendered (founder, 2026-03-01; supersedes prior DEFER). D005 production pilot COMPLETE (PR #452 merged into dev, 2026-03-01) under D004 constraints. **G8 PASS (classification gate, caveated, 2026-03-03).** All four primitives classified REDUCIBLE_WITH executable evidence (D001 analytical + D002-D003 + D005-D010 executable). G8 PASS closes classification evidence, not L4 completion. L4 remains blocked by stop conditions #3 (host for-loop) and #4 (L3-to-L4 gap). No production reduction claims. Research-evidence precedent locked: research analog evidence sufficient for classification gates; production claims require separate productionization gates (cross-substrate parity, performance profiling, migration tooling). Productionization gate lock: D009 requires memoization/cycle-detection parity + cross-substrate + node-count vs per-level reconciliation; D010 requires int-range + NaN/Inf + JS decoder + migration + integrity-chain. P6 decided (Option A, PR #456). P4 hotspot measured and DEFERRED (2026-03-02, PR #458).

**Legacy Surface Tracker (Round 19D, 2026-02-14):**
Decision record: `mu/docs/core/LegacySurfaceDecisionRecord.v0.md`
- `rcx_pi_rust/` — ARCHIVED Round 23A (moved to `archive/rcx_pi_rust/`)
- `rcx_omega/` — ARCHIVED Round 23A (moved to `archive/rcx_omega/`)
- `mu/worlds_json/` — MAINTAIN as test fixtures (moved from root Round 23B); `rcx_core_mut4.json` removed Round 22J (was byte-identical to mut3)
- `Makefile` — ARCHIVED Round 23E (moved to `archive/root_legacy/`)
- `rcx_runtime.py` — ARCHIVED Round 23E (moved to `archive/root_legacy/`)
- `rcx_start.py` — ARCHIVED Round 23E (moved to `archive/root_legacy/`)
- `.rcx_manifest.json` — UNTRACKED Round 23F (generated artifact, stays on disk)
- `archive/rcx_pi_rust/sanity_test/target/` — UNTRACKED Round 23F (23 Rust build artifacts)
- `archive/docs/latex/rcx-pi-paper.pdf` — UNTRACKED Round 23F (gitignored by `*.pdf`)
- Round 24A: Deleted 5 dead archive files (corpus/, normalized_prototype/, prototypes/); archived 6 deprecated scripts to `archive/scripts_deprecated/`; archived 3 stale roadmap gate docs to `archive/docs/`
- Round 24B: Recursive subfolder sweep — fixed DeepStep.v0.md stale refs; deleted moves_22b_specs.json (stale); deleted archive/scripts_deprecated/ (6 files); deleted 31 agent archive files (tools/, docs/, .claude/); deleted 16 zero-ref archive/docs/ files; cleaned governance exclusion patterns
- Round 24C: docs/ + roadmap/ → mu/docs/ convergence — 96 active files moved to `mu/docs/` (core, agents, cli, schemas, fixtures, execution, audit, reviews, roadmap), 41 files archived to `archive/docs/` + `archive/roadmap/`. Both `docs/` and `roadmap/` directories fully emptied. 231 path rewrites across 161 files. All 14 seed checksums updated (Python + JS). `enforce_tracker_sync.sh` updated to exclude `mu/docs/` from core-change detection. 5 test files with hardcoded `docs/` Path() references fixed. Reclassification guard enforced: zero-ref proof required for every ARCHIVE candidate
