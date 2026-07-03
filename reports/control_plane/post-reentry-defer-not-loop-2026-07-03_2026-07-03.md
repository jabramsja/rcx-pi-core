# Route a deferrable all-non-blocking post-reentry supervisor veto to defer-and-commit instead of an infinite Phase-B re-entry loop

Date: 2026-07-03
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: post-reentry-defer-not-loop-2026-07-03
Phase-A-Lock: LOCKED
Purpose: STRUCTURAL pipeline-hardening (#13; the #46/#62 post_reentry loop gap). ROOT (code-verified on dev): recovery_gate.fix_post_reentry_needs_phase_b handles a post-reentry supervisor NEEDS_PHASE_B veto by ALWAYS seeding a plain Phase-B resume and returning last_action='resume_phase_b_reentry' -- EVEN when the veto is over ONLY deferrable (non-high/critical, all_non_blocking) findings. When the re-entered Phase B re-emits the SAME non-blocking finding (e.g. a control-packet prose line-ref the FIX-25 normalizer does not strip), the supervisor vetoes again, recovery re-seeds a plain resume again, and the wave LOOPS (3+ NEEDS_PHASE_B cycles, recovered=True each time, never converging) -- forcing a hand-finish on every affected wave. The defer-and-commit machinery ALREADY EXISTS and must be REUSED, not duplicated: recovery_gate._write_recovery_deferred_non_blocking_packet (writes the canonical deferred non-blocking packet in the same lane Phase B uses), the all_non_blocking carry-forward already threaded into the resume_state, recovery_gate._finding_is_deferrable_on_go / the SINGLE deferrability rule, and phase_b_executor._disposition_for_finding + _shared_deferrable_on_go (the #19b path: a GO with only sub-floor deferrable findings DEFERS + proceeds to commit). There is NO ROUTE_COMMIT decision -- commit happens inside Phase B after a GO -- so the fix routes the deferrable-veto re-entry with the finding PRE-DEFERRED (deferred packet written + all_non_blocking carried) so the #19b _disposition_for_finding DEFERS it on the re-entry -> GO -> commit, instead of the plain resume that re-emits it and loops.

## Scope

mu/tools/executors/recovery_gate.py (fix_post_reentry_needs_phase_b) + a regression in the EXISTING mu/tests/tools/test_recovery_gate.py. When the post-reentry veto's findings are ALL deferrable (reuse _finding_is_deferrable_on_go / the all_non_blocking signal -- NO divergent local rule), route through the EXISTING _write_recovery_deferred_non_blocking_packet + all_non_blocking carry-forward so the ROUTE_PHASE_B re-entry defers the finding (via phase_b _disposition_for_finding) and commits, instead of last_action='resume_phase_b_reentry'. Preserve: a genuine high/critical or truly-blocking veto still resumes Phase B; a real reviewer/adapter crash still strands (fail-closed). Add a bounded loop-guard GATED on deferrability: if post_reentry_prior_bridge_rounds already shows a prior post_reentry cycle for the same wave AND the veto is all-deferrable (same _finding_is_deferrable_on_go / all_non_blocking signal -- no divergent rule), defer-and-commit (do not resume again); a high/critical or truly-blocking repeat veto is NEVER defer-and-committed by the loop-guard and stays on the fail-closed resume path, so the loop-guard can never auto-commit a blocking finding. No runtime/substrate files; L4_ENABLER.

Files and surfaces in scope:

- TASKS.md -- tracker-sync authority. The 2026-07-03 tracker sync note for wave `post-reentry-defer-not-loop-2026-07-03` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/post-reentry-defer-not-loop-2026-07-03_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. In `mu/tools/executors/recovery_gate.py::fix_post_reentry_needs_phase_b`, classify the post-reentry NEEDS_PHASE_B veto: detect the ALL-deferrable case by REUSING the existing `_finding_is_deferrable_on_go` / the `all_non_blocking` signal already threaded into the resume_state. Do NOT add a new or divergent local deferrability rule.
2. For the all-deferrable case, route the re-entry through the EXISTING `_write_recovery_deferred_non_blocking_packet` + `all_non_blocking` carry-forward so Phase B re-enters with the finding PRE-DEFERRED, letting `phase_b_executor._disposition_for_finding` / `_shared_deferrable_on_go` (the #19b path) DEFER it -> GO -> commit, instead of returning `last_action='resume_phase_b_reentry'`.
3. Add a bounded loop-guard GATED on deferrability (NOT a bare prior-round count): when `post_reentry_prior_bridge_rounds` already records a prior post_reentry cycle for the same wave AND the veto is all-deferrable (the SAME `_finding_is_deferrable_on_go` / `all_non_blocking` signal from WI1 -- no divergent rule), defer-and-commit so the deferrable wave cannot re-emit-and-loop. A high/critical or truly-blocking repeat veto MUST NOT be defer-and-committed by the loop-guard; it stays on the fail-closed resume path (WI4), so the loop-guard can never auto-commit a blocking finding.
4. Preserve the fail-closed branches unchanged: a genuine high/critical or truly-blocking veto still returns a plain Phase-B resume -- EVEN on a repeat post_reentry cycle, where the loop-guard (WI3) must defer to this path and never override it into a defer-and-commit; a real reviewer/adapter crash still strands.
5. Add a regression to the EXISTING `mu/tests/tools/test_recovery_gate.py` (hermetic, isolated tmp repos) asserting all five behaviors: (a) an all-non-blocking veto defers-and-commits (no `resume_phase_b_reentry`); (b) the loop-guard defers on a repeat post_reentry cycle WHEN the veto is all-deferrable; (c) a high/critical veto still resumes; (d) a reviewer/adapter crash still strands; (e) the intersection -- a REPEAT post_reentry cycle carrying a high/critical (non-deferrable) veto does NOT defer-and-commit but stays on the fail-closed resume path, proving the loop-guard is gated on deferrability, not a bare prior-round count.

## Constraints

- No runtime/substrate files. This is an `L4_ENABLER` (tracker note, target_gate_id G8); it MUST NOT touch runtime dirs -- only the control-plane surface `mu/tools/executors/recovery_gate.py` and its test.
- No new or divergent deferrability rule: reuse the SINGLE existing `_finding_is_deferrable_on_go` / `all_non_blocking` signal. Do NOT duplicate the defer-and-commit machinery (`_write_recovery_deferred_non_blocking_packet`, the carry-forward, `_disposition_for_finding`) -- REUSE it.
- No new `ROUTE_COMMIT` decision. Commit happens inside Phase B after a GO; this fix only PRE-DEFERS the finding on re-entry -- it does not introduce a commit route or bypass Phase B.
- Do NOT change high/critical or true-blocking veto behavior, nor the real-crash strand path. Fail-closed must be preserved: the loop-guard is gated on deferrability, NOT a bare prior-round count -- it may defer-and-commit ONLY the all-deferrable case, and must never defer-and-commit a high/critical / truly-blocking veto even on a repeat post_reentry cycle (that intersection would otherwise be a fail-closed hole).
- Only two files change: `mu/tools/executors/recovery_gate.py` + `mu/tests/tools/test_recovery_gate.py`. `TASKS.md` is tracker-sync authority only, not a hand-edited code surface here.
- No other executor/pipeline surfaces and no doc-governance-owned state files (STATUS.md, TASKS.md ownership) are in scope.

## Stop conditions

- Stop when the evidence_command (`test_recovery_gate.py`) passes AND the regression covers all five behaviors: all-deferrable defer-and-commit, all-deferrable loop-guard defer, high/critical resume, crash strand, and the high/critical-on-repeat-cycle intersection (no defer-and-commit).
- Stop and re-scope (do NOT proceed) if the change would require touching a runtime/substrate dir or introducing a new deferrability rule -- that signals the fix has drifted out of `L4_ENABLER` scope.
- Stop and escalate as POLICY_BOUND (founder decision) if the existing `_write_recovery_deferred_non_blocking_packet` / `all_non_blocking` carry-forward cannot be reused as-is and would force duplicating the machinery.
- Do not push/merge from Phase A; this packet is design-only until agent-reviewed and bridge-converged.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py`

## Acceptance criteria

- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_recovery_gate.py -p no:xdist -q` passes (the G8 evidence_command).
- A deferrable / `all_non_blocking` post-reentry veto routes through the existing deferred-packet + carry-forward so the re-entry DEFERS the finding (#19b) and commits: `fix_post_reentry_needs_phase_b` no longer returns `last_action='resume_phase_b_reentry'` for the all-deferrable case.
- Bounded loop-guard proven AND gated on deferrability: once a prior post_reentry cycle is recorded for the same wave (`post_reentry_prior_bridge_rounds`), an all-deferrable veto defers-and-commits; a high/critical / truly-blocking veto on that same repeat cycle does NOT defer-and-commit but stays on the fail-closed resume path -- the loop-guard is not a bare count and can never auto-commit a blocking finding.
- High/critical and real reviewer/adapter-crash paths are unchanged (fail-closed), asserted by the regression -- including on a repeat post_reentry cycle (the loop-guard/high-critical intersection defers to the resume path, not defer-and-commit).
- Only `mu/tools/executors/recovery_gate.py` + `mu/tests/tools/test_recovery_gate.py` are touched; no runtime/substrate files.
- The #46/#62 post_reentry loop is closed: an all-non-blocking veto no longer produces 3+ non-converging NEEDS_PHASE_B cycles / per-wave hand-finish.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `post-reentry-defer-not-loop-2026-07-03`.
- Governing packet: this file, `reports/control_plane/post-reentry-defer-not-loop-2026-07-03_2026-07-03.md`.
- TASKS.md authority: the 2026-07-03 tracker sync note for wave `post-reentry-defer-not-loop-2026-07-03` is canonical for this packet's L4 fields.
- Authorization: Founder-directed structural pipeline-hardening 2026-07-03 (#13; standing directive #5 any-issue->structural-fix; the #62 post_reentry loop forced hand-finishes this session). FOUNDER_OVERRIDE:post-reentry-defer-not-loop-2026-07-03.

FOUNDER_OVERRIDE:post-reentry-defer-not-loop-2026-07-03

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `post-reentry-defer-not-loop-2026-07-03`
- Active packet: `reports/control_plane/post-reentry-defer-not-loop-2026-07-03_2026-07-03.md`
- Indicator artifact: `reports/l4_wave_indicators/post-reentry-defer-not-loop-2026-07-03.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/post-reentry-defer-not-loop-2026-07-03_2026-07-03.md`
  - `reports/deferred/non_blocking/post-reentry-defer-not-loop-2026-07-03_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/post-reentry-defer-not-loop-2026-07-03.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `post-reentry-defer-not-loop-2026-07-03`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/post-reentry-defer-not-loop-2026-07-03_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/post-reentry-defer-not-loop-2026-07-03.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id post-reentry-defer-not-loop-2026-07-03 --output reports/l4_wave_indicators/post-reentry-defer-not-loop-2026-07-03.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/post-reentry-defer-not-loop-2026-07-03_2026-07-03.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_recovery_gate.py`, `mu/tools/executors/recovery_gate.py`, `reports/control_plane/post-reentry-defer-not-loop-2026-07-03_2026-07-03.md`, `reports/deferred/non_blocking/post-reentry-defer-not-loop-2026-07-03_bridge_nonblockers.md`, `reports/l4_wave_indicators/post-reentry-defer-not-loop-2026-07-03.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: post-reentry-defer-not-loop-2026-07-03.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `post-reentry-defer-not-loop-2026-07-03`
- Active packet: `reports/control_plane/post-reentry-defer-not-loop-2026-07-03_2026-07-03.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `b287012ee2725bd00a8241fc9cdf35a455530ea83dc565a00c9d0f31bae9971c`
- Indicator artifact: `reports/l4_wave_indicators/post-reentry-defer-not-loop-2026-07-03.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/post-reentry-defer-not-loop-2026-07-03_2026-07-03.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_recovery_gate.py`, `mu/tools/executors/recovery_gate.py`, `reports/control_plane/post-reentry-defer-not-loop-2026-07-03_2026-07-03.md`, `reports/deferred/non_blocking/post-reentry-defer-not-loop-2026-07-03_bridge_nonblockers.md`, `reports/l4_wave_indicators/post-reentry-defer-not-loop-2026-07-03.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/post-reentry-defer-not-loop-2026-07-03.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/post-reentry-defer-not-loop-2026-07-03_2026-07-03.md`
  - `reports/deferred/non_blocking/post-reentry-defer-not-loop-2026-07-03_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/post-reentry-defer-not-loop-2026-07-03.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
