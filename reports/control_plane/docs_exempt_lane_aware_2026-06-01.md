# Docs Exempt Lane Aware 2026-06-01

Date: 2026-06-01
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: docs-exempt-lane-aware-2026-06-01
Phase-A-Lock: LOCKED
Class: L4_ENABLER (tooling / docs-governance / tests; no runtime dir)
Purpose: Make doc-governance exempt patterns lane-aware. In mu/tools/docs/docs_registry.json (tools/docs is a symlink to mu/tools/docs; one canonical file), the exempt_patterns entry "^\\.agent_bus/" matches the default agent bus directory but NOT a parallel-lane bus like .agent_bus-lane1/ or .agent_bus-lane2/. As a result classify_md_path (in mu/tools/docs/shared_doc_config.py) classifies a lane bus's own generated bridge transcripts (.agent_bus-lane<N>/rendered/*.md) as 'unknown', docs_sync_report flags them unclassified, check_docs_consistency.sh exits 1, and the pre-commit supervisor returns a critical docs_consistency failure that blocks COMMIT_GO. This blocked BOTH live parallel-lane waves (standalone-commit-evidence-guard and claude-pager-route-both) on 2026-06-01; the Codex meta-review independently prescribed updating the docs sync classification/ignore rules so generated agent-bus rendered markdown is not treated as unclassified docs. The same agent-bus-only assumption is independently hardcoded in the module-level EXEMPT_PATTERNS list in mu/tests/docs/test_doc_governance.py (consumed by is_exempt() and applied across get_all_md_files() / REPO_ROOT.rglob("*.md")), so the same lane-bus rendered doc also stays non-exempt in the pytest governance scanner that the wave's own evidence command runs. Fix: broaden the agent-bus exempt entry to also match .agent_bus-<lane> buses in BOTH independent sources (docs_registry.json and test_doc_governance.py).

## Scope

Broaden the agent-bus exempt entry from the bus-only form (docs_registry.json: `"^\\.agent_bus/"`; test_doc_governance.py: `r"^\.agent_bus/"`) to the lane-aware form (docs_registry.json: `"^\\.agent_bus(-[A-Za-z0-9_-]+)?/"`; test_doc_governance.py: `r"^\.agent_bus(-[A-Za-z0-9_-]+)?/"`) so doc-governance exempts both the default `.agent_bus` and any parallel-lane `.agent_bus-<lane>` bus.

This must be applied to BOTH independent sources of the exempt list, because neither is derived from the other (their pattern lists have different contents):
1. `exempt_patterns` in `mu/tools/docs/docs_registry.json`, consumed by `classify_md_path` in `mu/tools/docs/shared_doc_config.py` — the `docs_sync_report` / `check_docs_consistency.sh` / pre-commit-supervisor path.
2. The module-level `EXEMPT_PATTERNS` list in `mu/tests/docs/test_doc_governance.py`, consumed by `is_exempt()` and applied to every path returned by `get_all_md_files()` (`REPO_ROOT.rglob("*.md")`) — the `pytest mu/tests/docs` governance path that the wave's own evidence command runs.

Fixing only `docs_registry.json` would leave lane-bus rendered transcripts non-exempt in the pytest scanner, where they are counted as non-exempt, non-governed docs that dilute the governance-coverage ratio (the test file's own docstring states runtime artifacts must not dilute it). Broadening both sources unblocks EVERY parallel-lane wave's commit (any lane bus accumulates rendered bridge transcripts that an unbroadened scanner otherwise flags as unclassified / non-exempt, failing docs_consistency at the pre-commit supervisor). The `docs_registry.json` change is one canonical JSON file (`tools/docs` symlinks to `mu/tools/docs`); the `test_doc_governance.py` change edits its hardcoded `EXEMPT_PATTERNS` in place. The `.scratch/` sibling pattern needs no change (no per-lane scratch variant). Tooling/docs-governance and tests only; no runtime dir (L4_ENABLER). Cite code by function name and file only, no line numbers.

In-scope surfaces:
- `mu/tools/docs/docs_registry.json` `exempt_patterns` (the single canonical registry file; `tools/docs` is a symlink to `mu/tools/docs`) — broaden the agent-bus entry.
- `EXEMPT_PATTERNS` (module-level list) in `mu/tests/docs/test_doc_governance.py` — broaden the agent-bus entry to the same lane-aware form. This is a second, independent source of the exempt list (its contents are not derived from `docs_registry.json`), consumed by `is_exempt()` and applied across `get_all_md_files()` (`REPO_ROOT.rglob("*.md")`).
- `classify_md_path` in `mu/tools/docs/shared_doc_config.py` and `is_exempt()` in `mu/tests/docs/test_doc_governance.py` (consumers of the respective exempt lists — read-only for logic; the change is data-only in each list, no consumer-logic change expected).
- Regression coverage under `mu/tests/docs/` asserting a `.agent_bus-lane<N>/rendered/*.md` path is exempt in BOTH paths: `classify_md_path` returns the exempt classification AND `is_exempt()` returns True (with the default `.agent_bus/` path still exempt in both). Prefer adding the `is_exempt()` assertion inside the existing `mu/tests/docs/test_doc_governance.py` to avoid a new test-file growth-cap bump where practical.

- `reports/deferred/non_blocking/docs-exempt-lane-aware-2026-06-01_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work Items

Work items are the concrete bounded tasks for the current phase of [NEXT-CODEX-POST-REDTEAM], drawn from the TASKS.md tracker note for this wave (2026-06-01, docs-exempt-lane-aware-2026-06-01). None of the blocking review findings prove any item is already landed; the round-2 finding adds work item 2 below (the second, independent docs-governance scanner that carries the same agent-bus-only assumption). All items remain pending.

1. **Broaden the registry exempt pattern.** In `mu/tools/docs/docs_registry.json`, change the agent-bus `exempt_patterns` entry from `"^\\.agent_bus/"` to `"^\\.agent_bus(-[A-Za-z0-9_-]+)?/"`. Single canonical file only (do not edit through the `tools/docs` symlink as a second file). Keep the regex anchored to the `.agent_bus` prefix so only bus paths are matched.
2. **Broaden the pytest-governance exempt pattern.** In `mu/tests/docs/test_doc_governance.py`, change the agent-bus entry in the module-level `EXEMPT_PATTERNS` list from `r"^\.agent_bus/"` to `r"^\.agent_bus(-[A-Za-z0-9_-]+)?/"` (Python raw-string escaping, mirroring the registry change). This list is independent of `docs_registry.json` and is consumed by `is_exempt()` across `get_all_md_files()` (`REPO_ROOT.rglob("*.md")`); without this change a `.agent_bus-lane<N>/rendered/*.md` file stays non-exempt in the pytest scanner and dilutes the governance-coverage ratio. This edits a test file, not a runtime dir (L4_ENABLER preserved).
3. **Add regression coverage.** Under `mu/tests/docs/`, assert a `.agent_bus-lane<N>/rendered/*.md` path is exempt in BOTH paths — `classify_md_path` returns the exempt classification AND `is_exempt()` returns True — and that the default `.agent_bus/` path remains exempt in both. Prefer adding the `is_exempt()` assertion inside the existing `mu/tests/docs/test_doc_governance.py` to avoid a new test-file growth-cap bump where practical. Cite code by function name and file only.
4. **Run the wave evidence gate.** Confirm the evidence command of record — `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs && ./tools/checks/check_docs_consistency.sh` — passes (note `pytest mu/tests/docs` runs the `test_doc_governance.py` scanner, so it gates work item 2), and that `docs_sync_report` reports zero unclassified for a tree containing a `.agent_bus-lane2/rendered/*.md` file.
5. **Collect the indicator artifact.** Run `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id docs-exempt-lane-aware-2026-06-01 --output reports/l4_wave_indicators/docs-exempt-lane-aware-2026-06-01.json` to bind the wave to its L4 indicator.

## Constraints

Out of scope (do NOT do in this wave):
- **No runtime-dir changes.** This is `Class: L4_ENABLER`; touching a runtime/substrate dir would violate the L4 execution contract. The change is data-only in a docs-governance registry plus a test-file pattern list and regression coverage.
- **No change to the `.scratch/` sibling pattern.** There is no per-lane scratch variant, so it needs no broadening.
- **Bound the change to the two identified exempt-list sources.** Exactly two independent sources carry the agent-bus-only assumption and are in scope: `exempt_patterns` in `mu/tools/docs/docs_registry.json` and `EXEMPT_PATTERNS` in `mu/tests/docs/test_doc_governance.py`. Do NOT refactor `classify_md_path` / `is_exempt()` logic, do NOT touch executors, and do NOT attempt to centralize/dedupe the two lists in this wave. If a THIRD independent source surfaces, STOP and escalate (see Stop Conditions) rather than silently widening.
- **No new control-plane files.** Replace this stub in place; the only potential new artifact is regression coverage under `mu/tests/docs/` (prefer folding assertions into the existing `test_doc_governance.py` to avoid a new file). Editing `docs_registry.json` and the existing `test_doc_governance.py` adds no new files. Do not create additional packets or reports.
- **No relisting of already-landed [NEXT-CODEX-POST-REDTEAM] items.** Per the TASKS.md queue note, the engine-state/scheduler seed, fixture, structural-test, and scheduler-parity items already landed; they are unrelated to this docs-governance fix and must not be re-listed here.
- **No line numbers in docs; no hardcoded counts.** Cite code by function and file name only.
- **Do not begin Phase B implementation in Phase A.** This packet defines the plan; implementation follows after bridge convergence and Phase-A-Lock.

## Stop Conditions

Stop and escalate (do not work around) if any of the following fire:
1. **Non-bus reclassification.** If either broadened regex would change the classification of any markdown path that is NOT under an agent bus (i.e., the pattern is no longer effectively anchored to the `.agent_bus` prefix), STOP and treat it as POLICY_BOUND — present to founder.
2. **Residual non-exempt lane-bus docs after both fixes.** If, after broadening BOTH identified sources, `pytest mu/tests/docs` / `docs_sync_report` / `check_docs_consistency.sh` still report a lane-bus rendered doc as unclassified or non-exempt, STOP — this indicates a THIRD independent source of the agent-bus-only assumption beyond the two now in scope. Re-open scope as a separate finding/packet; do NOT widen this packet to chase it.
3. **Runtime-dir pressure.** If implementing the fix appears to require touching any runtime/substrate dir, STOP — that would break the L4_ENABLER class invariant. Escalate.
4. **Growth-cap collision.** If adding regression coverage under `mu/tests/docs/` as a new test file would exceed a growth cap, STOP and surface the need for a documented `FOUNDER_OVERRIDE` test-file bump rather than silently dropping the test (folding the `is_exempt()` assertion into the existing `test_doc_governance.py` avoids the bump where practical).
5. **Any POLICY_BOUND conflict.** Founder is the override authority; present the decision and wait.

Phase A is complete only when this packet carries all required sections (Scope, Work items, Constraints, Stop conditions, Acceptance criteria, Grounding/Authorization) and the bridge converges. Phase-A-Lock remains UNLOCKED until then.

## Acceptance Criteria

The wave is accepted when ALL hold:
1. **Both sources match both buses.** Both exempt lists match `.agent_bus/` and `.agent_bus-<lane>/`: `classify_md_path` (via `mu/tools/docs/docs_registry.json`) returns the exempt classification for a `.agent_bus-lane<N>/rendered/*.md` path, and `is_exempt()` (via `EXEMPT_PATTERNS` in `mu/tests/docs/test_doc_governance.py`) returns True for the same path. The default `.agent_bus/` path remains exempt in both.
2. **Evidence gate green.** The evidence command of record `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs && ./tools/checks/check_docs_consistency.sh` exits 0 (the `pytest mu/tests/docs` portion runs the `test_doc_governance.py` governance scanner, so a green gate confirms the second source is fixed).
3. **Zero unclassified for a lane tree.** `docs_sync_report` reports zero unclassified for a tree containing a `.agent_bus-lane2/rendered/*.md` file; `check_docs_consistency.sh` exits 0; the pre-commit supervisor no longer emits a critical docs_consistency failure for lane-bus rendered transcripts.
4. **Regression lock (both paths).** Regression coverage under `mu/tests/docs/` asserts the lane-bus-exempt result for BOTH `classify_md_path` and `is_exempt()`, and fails if either pattern regresses to bus-only.
5. **L4 binding.** No runtime dir is touched; the L4 execution-contract enforcer passes for `Class: L4_ENABLER`; the indicator artifact `reports/l4_wave_indicators/docs-exempt-lane-aware-2026-06-01.json` is collected via the indicator command.

## Grounding / Authorization

**TASKS.md authorization.** This wave is grounded by the TASKS.md tracker sync note (2026-06-01, `docs-exempt-lane-aware-2026-06-01`), which declares `Class: L4_ENABLER`, `target_gate_id: G8`, and `Packet: reports/control_plane/docs_exempt_lane_aware_2026-06-01.md` (this file). Evidence command of record: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs && ./tools/checks/check_docs_consistency.sh` — which exercises both in-scope exempt-list sources (the `pytest mu/tests/docs` portion runs `test_doc_governance.py`; `check_docs_consistency.sh` runs the `classify_md_path` path).

**Queue.** Work proceeds under the founder-authorized `[NEXT-CODEX-POST-REDTEAM]` queue in TASKS.md (UNPARKED 2026-03-28, tracked packet `reports/control_plane/post_redteam_structural_queue_2026-03-20.md`). That queue is OPEN only for future bounded packets; this docs-governance fix is one such bounded downstream packet and does not relist the already-landed engine-state/scheduler slice.

**Governing packet.** This file (`reports/control_plane/docs_exempt_lane_aware_2026-06-01.md`) is the governing packet for the wave, as named in the TASKS.md tracker note above.

**Authorization (commit-derivable).** This is a control-surface L4_ENABLER pipeline-bug fix. Authorization: standing pipeline-bug-fix authorization per memory feedback_autonomous_executor_fix.md. The same-wave override token, matching the TASKS.md tracker note verbatim so commit automation can derive it mechanically, is:

`FOUNDER_OVERRIDE:docs-exempt-lane-aware-2026-06-01 (standing pipeline-bug-fix authorization per memory feedback_autonomous_executor_fix.md)`

**L4 metadata (mirrors the TASKS.md tracker note).**
- primary_blocker_class: INTEGRATION
- primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION
- indicator_artifact_ref: reports/l4_wave_indicators/docs-exempt-lane-aware-2026-06-01.json
- indicator_collection_command: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id docs-exempt-lane-aware-2026-06-01 --output reports/l4_wave_indicators/docs-exempt-lane-aware-2026-06-01.json
- bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP
- boot0_track_id: V1
- boot0_progress_state: HOLD

## Request from Post-Merge Supervisor (provenance)

Make doc-governance exempt patterns lane-aware. In mu/tools/docs/docs_registry.json (tools/docs is a symlink to mu/tools/docs; one canonical file), the exempt_patterns entry "^\\.agent_bus/" matches the default agent bus directory but NOT a parallel-lane bus like .agent_bus-lane1/ or .agent_bus-lane2/. As a result classify_md_path (in mu/tools/docs/shared_doc_config.py) classifies a lane bus's own generated bridge transcripts (.agent_bus-lane<N>/rendered/*.md) as 'unknown', docs_sync_report flags them unclassified, check_docs_consistency.sh exits 1, and the pre-commit supervisor returns a critical docs_consistency failure that blocks COMMIT_GO. This blocked BOTH live parallel-lane waves (standalone-commit-evidence-guard and claude-pager-route-both) on 2026-06-01; the Codex meta-review independently prescribed updating the docs sync classification/ignore rules so generated agent-bus rendered markdown is not treated as unclassified docs. Fix: broaden the exempt pattern to also match .agent_bus-<lane> buses.

Routed next-candidate:
docs-exempt-lane-aware-2026-06-01

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `docs-exempt-lane-aware-2026-06-01`
- Active packet: `reports/control_plane/docs_exempt_lane_aware_2026-06-01.md`
- Indicator artifact: `reports/l4_wave_indicators/docs-exempt-lane-aware-2026-06-01.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/docs/test_doc_governance.py`
  - `mu/tools/docs/docs_registry.json`
  - `reports/control_plane/docs_exempt_lane_aware_2026-06-01.md`
  - `reports/deferred/non_blocking/docs-exempt-lane-aware-2026-06-01_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/docs-exempt-lane-aware-2026-06-01.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `docs-exempt-lane-aware-2026-06-01`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/docs-exempt-lane-aware-2026-06-01_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `docs-exempt-lane-aware-2026-06-01`
- Active packet: `reports/control_plane/docs_exempt_lane_aware_2026-06-01.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `dc7e5b7bab2b7a623a0843138afe53e9030c14a24fec150e3bb4f355d4614eb0`
- Indicator artifact: `reports/l4_wave_indicators/docs-exempt-lane-aware-2026-06-01.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_doc_governance.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/docs_exempt_lane_aware_2026-06-01.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/docs-exempt-lane-aware-2026-06-01.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/docs/test_doc_governance.py`
  - `mu/tools/docs/docs_registry.json`
  - `reports/control_plane/docs_exempt_lane_aware_2026-06-01.md`
  - `reports/deferred/non_blocking/docs-exempt-lane-aware-2026-06-01_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/docs-exempt-lane-aware-2026-06-01.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
