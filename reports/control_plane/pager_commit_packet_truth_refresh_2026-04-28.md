# Pager Commit Packet Truth Refresh

Date: 2026-04-28
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Task: [PIPELINE-AGENT-PAGER]
Wave ID: pager-commit-packet-truth-refresh-2026-04-28
Phase-A-Lock: LOCKED
Wave class: L4_ENABLER
Target gate: G8

## Purpose

Mechanize the still-open `[PIPELINE-AGENT-PAGER]` follow-on from
`TASKS.md`: commit-ready packet truth can drift after `commit_executor` mutates
or advances the commit path. The commit path must refresh wave-bound packet
truth, handoff staging scope, and staged L4 proof before supervisor review and
push so a later operator does not need to manually repair packet/report/tracker
narrative after the executor has changed the staged state.

This packet is a narrow control-surface follow-up. It does not widen runtime,
substrate, Mu semantics, Stage0 semantics, or bootstrap authority.

## Grounding / Observed Failure Truth

- `TASKS.md` keeps `[PIPELINE-AGENT-PAGER]` in progress and records the
  2026-04-22 mechanization follow-on: commit-ready packet truth drifted after
  `commit_executor` inserted `TASKS.md`, staged an L4 indicator artifact, and
  later advanced the commit path while the packet still described an older
  narrower Phase B scope.
- At packet lock time, the commit executor still had the structural shape that
  required a refresh layer: Step 3 mutates or inserts the tracker note, Step 4
  stages only `handoff["files_to_stage"]` plus `force_add_files`, Step 5
  collects/stages the indicator artifact, and Step 5b reconciles only
  `indicator_artifact_ref` in `TASKS.md`. This packet adds Step 5c for packet
  truth refresh and handoff-scope rebinding before supervisor packaging.
- The handoff builder exists and must remain the canonical mechanism:
  `mu/tools/executors/commit_executor.py:3994` defines
  `build_commit_handoff()`, and Phase B calls that builder through
  `mu/tools/executors/phase_b_executor.py:2539`.

## Scope

Admitted files and directories:

1. `TASKS.md`
2. `reports/control_plane/pager_commit_packet_truth_refresh_2026-04-28.md`
3. `mu/tools/executors/commit_executor.py`
4. `mu/tools/executors/phase_b_executor.py`
5. `mu/tools/executors/executor_dispatch.py`
6. `mu/tools/executors/recovery_gate.py`
7. `mu/tools/executors/tracker_sync_note.py`
8. `mu/tests/tools/test_commit_executor_receipt.py`
9. `mu/tests/tools/test_executor_dispatch.py`
10. `mu/tests/tools/test_phase_b_executor.py`
11. `mu/tools/observability/_pane_timeline.sh`
12. `mu/tests/tools/test_recovery_gate.py`
13. `reports/deferred/non_blocking/pager-commit-packet-truth-refresh-2026-04-28_bridge_nonblockers.md`
14. `reports/l4_wave_indicators/pager-commit-packet-truth-refresh-2026-04-28.json`

## Work Items

1. Add a deterministic commit-path refresh step before the pre-commit
   supervisor package is built. The refresh must use executor-owned facts:
   tracker note text, the final staged path set, indicator artifact path,
   supervisor/commit status, validation/evidence handles, and the active
   packet path.
2. Refresh the tracked packet narrative for same-wave commit-path additions
   without broad markdown rewriting. It is enough to append or replace a
   bounded "Commit Path Truth Refresh" block that names the current staged
   file set, indicator artifact, validation handles, and commit status.
3. Rebind handoff staging scope after the refresh so same-wave packet changes,
   tracker follow-up changes, and generated indicator artifacts are staged
   mechanically before supervisor review and push.
4. Preserve fail-closed behavior. If packet refresh cannot be performed for a
   packet-bound L4 control-surface wave, the commit path must stop with a
   targeted error naming the missing or invalid refresh input instead of
   pushing stale packet truth.
5. Add focused tests that reproduce the drift shape without invoking GitHub:
   Step 3 changes `TASKS.md`, Step 5 adds an indicator artifact, and the
   commit path refreshes packet/handoff truth before supervisor packaging.
6. Keep `build_commit_handoff()` as the canonical handoff builder. Do not
   introduce a second hand-authored handoff format.
7. Update `TASKS.md` and this packet with the implementation and validation
   truth after Phase B convergence.
8. Keep pane 4 pager/autoping observability visible in the terminal viewport
   after long timelines; the status block must not scroll off the top when
   timeline history grows.

## Constraints

- Do not disable or bypass Gate 8, pre-push, L4 indicator collection,
  pre-commit supervisor review, receipt validation, or GitHub bot review.
- Do not make pane text, logs, dashboard rendering, or tmux scraping the source
  of packet truth.
- Do not edit Claude-local surfaces.
- Do not widen the `[PIPELINE-AGENT-PAGER]` lane into parallel-pipeline
  namespacing or multi-worktree dashboard allocation.
- Do not replace `build_commit_handoff()` with ad hoc JSON writes for normal
  commit handoffs.

## Stop Conditions

1. Stop and split if the implementation requires changing runtime/substrate
   code outside executor/control-plane surfaces.
2. Stop and split if packet truth refresh requires a general markdown AST
   rewrite framework instead of a bounded wave-owned block.
3. Stop and split if correct staging scope requires solving unrelated dirty
   worktree policy outside this packet.

## Acceptance Criteria

1. Commit-path packet refresh is deterministic, idempotent, and covered by
   focused tests.
2. A packet-bound L4 control-surface commit cannot reach pre-commit supervisor
   review with a stale packet narrative after `TASKS.md` or the L4 indicator
   artifact was added by the commit path.
3. Same-wave packet changes and generated indicator artifacts are mechanically
   included in the staged set before supervisor review and push.
4. Failure cases name the root missing input or invalid state, not a generic
   "manual repair required" message.
5. `TASKS.md`, this packet, the handoff, and the L4 indicator artifact agree on
   changed files, wave class, target gate, validation commands, and residual
   risks before commit.
6. Pane 4 shows Autoping status/detail/summary and Pager wake/detail/state near
   the bottom status area so the latest pager/autoping times remain visible in
   a normal tmux viewport.

## Suggested Validation

- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py -k 'packet or truth or handoff or tracker'`
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_dispatch.py -k 'handoff or tracker or commit'`
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_phase_b_executor.py -k 'handoff or packet or tracker'`
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_recovery_gate.py -k 'post_reentry_needs_phase_b'`
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_recovery_gate.py -k 'pane_timeline_shows_last_pager_wake_summary'`
- `bash tools/checks/check_stale_next_items.sh`
- `./tools/checks/check_docs_consistency.sh`

## Phase B Implementation Truth

Implemented in the commit executor control path without widening runtime,
substrate, Mu, Stage0, or bootstrap authority.

- `commit_executor.py` now accepts an optional canonical `tracked_packet`
  handoff field and resolves the active control-plane packet only from
  `tracked_packet`; scope-only control-plane references remain inert.
- After Step 5 indicator collection and `TASKS.md` indicator reconciliation,
  Step 5c refreshes the active packet through a bounded
  `Commit Path Truth Refresh` block before Step 6 builds the pre-commit
  supervisor package.
- The refresh block is replace-only between explicit HTML markers, records the
  current staged path set, indicator artifact, pre-commit receipt/evidence
  handles, tracker-note hash, and pre-supervisor commit status, and fails closed
  with targeted diagnostics for missing packet, mismatched wave id, unbalanced
  markers, missing tracker note, or unstaged indicator input.
- The in-memory handoff is rebuilt through `build_commit_handoff()` after the
  packet refresh so Step 6 supervisor scope uses the final staged path set,
  including `TASKS.md`, same-wave packet edits, and the generated L4 indicator.
- `phase_b_executor.py` now threads `tracked_packet=plan_path` into canonical
  handoff construction only for real packet-backed plans; planless
  `ROUTING_RECORD_AUTHORITY` handoffs omit `tracked_packet` instead of binding
  the synthetic `<planless:...>` marker. `executor_dispatch.py` rejects stale
  Phase B handoffs in both direct `COMMIT_GO` dispatch and the Phase B→commit
  chained path when the routing record's tracked packet differs from the
  handoff packet identity, or when a planless chained handoff belongs to a
  different wave/task identity.
- `mu/tools/observability/_pane_timeline.sh` now prints the Autoping/Pager
  status block below the current status pointer, keeping latest autoping and
  pager wake timestamps visible after long timeline history scrolls.
- `phase_b_executor.py` now builds supervisor package and commit-handoff
  `bridge_status` from the maximum of executor-owned round state and documented
  same-wave remediation evidence in the active packet/TASKS entry, so a
  re-entered package cannot claim 1/1 convergence after the same staged wave
  already records three bridge remediations.
- `recovery_gate.py` now recognizes post-reentry `NEEDS_PHASE_B` payloads even
  when the dispatcher wraps the structured Phase B JSON inside `stdout`, then
  seeds the deterministic `needs_phase_b_reentry` checkpoint from that embedded
  payload so the retry runs in a fresh Phase B process. The checkpoint also
  preserves embedded deferred non-blocking packet paths from the merged payload
  instead of dropping them when the outer executor wrapper omits that field.
- `commit_executor.py` now keeps post-commit continuation records keyed to the
  original caller-supplied handoff hash after Step 5c refreshes the in-memory
  supervisor handoff. The refreshed hash is retained separately as
  `refreshed_handoff_sha`, so a later rerun with the same `--handoff` payload can
  resume at the post-commit continuation instead of re-entering Steps 3-10.

## Test Coverage

- `mu/tests/tools/test_commit_executor_receipt.py` reproduces the drift shape:
  Step 3 inserts `TASKS.md`, Step 5 stages an indicator artifact, Step 5c
  refreshes the packet, and Step 6 receives the refreshed staged file set and
  evidence handles before invoking the supervisor.
- `mu/tests/tools/test_commit_executor_receipt.py` also locks the targeted
  missing-packet fail-closed error, the scope-only inert path, and two-call
  refresh idempotence.
- `mu/tests/tools/test_commit_executor_receipt.py` also locks that Step 5c
  handoff refresh does not rotate the post-commit continuation key away from the
  original `--handoff` payload.
- `mu/tests/tools/test_phase_b_executor.py` locks Phase B propagation of
  `tracked_packet` into the canonical handoff builder for packet-backed plans
  and locks that planless commit-ready handoffs omit the synthetic plan marker
  from `tracked_packet`.
- `mu/tests/tools/test_phase_b_executor.py` also locks that the pre-commit
  supervisor package and final commit handoff use the documented same-wave
  bridge round floor when the staged packet/TASKS evidence records more
  remediation rounds than the resumed executor state.
- `mu/tests/tools/test_phase_b_executor.py` locks that TASKS-derived bridge
  remediation evidence is bounded to the current tracker entry and cannot be
  inflated by a later same-date wave.
- `mu/tests/tools/test_executor_dispatch.py` locks stale tracked-packet and
  planless wave/task handoff rejection before direct and chained commit
  execution.
- `mu/tests/tools/test_recovery_gate.py` locks that Autoping and Pager detail
  remain in the pane timeline's visible tail.
- `mu/tests/tools/test_recovery_gate.py` also locks dispatcher-wrapped
  post-reentry `NEEDS_PHASE_B` JSON as the Tier 1 resume path, including
  checkpoint seeding from the embedded payload and preservation of embedded
  deferred non-blocking packet paths.

## Bridge Round 1 Remediation

- Bridge Round 1 NO_GO found that `_continue_successful_executor_chain()` could
  invoke `commit_executor.py --handoff` after Phase B success without the stale
  `tracked_packet` handoff validation used by direct `COMMIT_GO` dispatch.
- The chained Phase B→commit path now runs `_validate_phase_b_handoff_identity()`
  whenever the routing record declares a tracked packet and fails closed before
  invoking commit if the packet identity mismatches.
- `mu/tests/tools/test_executor_dispatch.py::test_phase_b_chain_rejects_stale_handoff_tracked_packet`
  reproduces the stale handoff shape and asserts that the commit executor is not
  invoked.

## Bridge Round 2 Remediation

- Bridge Round 2 NO_GO found that planless Phase B commit-ready handoffs passed
  the synthetic `<planless:{wave_id}>` marker as `tracked_packet`, which the
  canonical `build_commit_handoff()` path correctly rejects because
  `tracked_packet` must name a real `reports/control_plane/*.md` packet.
- The final Phase B handoff call now passes `tracked_packet` only when
  `plan_path` is a real packet path; planless routing-record-authority handoffs
  remain packetless and therefore do not ask the commit path to refresh a
  non-existent control-plane packet.
- `mu/tests/tools/test_phase_b_executor.py::test_planless_commit_ready_omits_tracked_packet_from_handoff`
  drives a planless Phase B run to commit-ready handoff construction and asserts
  that `tracked_packet` is `None` while the synthetic marker remains only a
  non-authoritative scope item.

## Bridge Round 3 Remediation

- Bridge Round 3 NO_GO found that planless Phase B chained commits could still
  replay a stale handoff because `_continue_successful_executor_chain()` only
  invoked handoff identity validation when the routing record declared
  `tracked_packet`.
- The chained Phase B→commit path now runs
  `_validate_phase_b_handoff_identity()` whenever the routing record carries
  `wave_name`, `wave_id`, `task_id`, or `tracked_packet`, so planless
  routing-record-authority handoffs remain bound to wave/task identity before
  invoking `commit_executor.py --handoff`.
- `mu/tests/tools/test_executor_dispatch.py::test_phase_b_chain_rejects_planless_stale_handoff_identity`
  reproduces an `old-wave`/`[OLD]` handoff against a `current-wave`/`[CURRENT]`
  planless routing record and asserts that the commit executor is not invoked.

## Pre-commit Package Re-entry Remediation

- Pre-commit meta review found that the package `bridge_status` still claimed
  1/1 convergence while staged `TASKS.md` and this packet recorded the three
  same-wave bridge remediation rounds above.
- `phase_b_executor.py` now computes effective package/handoff bridge status
  from the maximum of `result["bridge_rounds"]` and bounded same-wave
  remediation evidence in the packet/TASKS text before both supervisor
  packaging and `prepare_commit_handoff()`.
- `mu/tests/tools/test_phase_b_executor.py::test_run_phase_b_handoff_bridge_status_uses_documented_round_floor`
  reproduces the drift shape and asserts both the supervisor package and final
  handoff report `{"rounds": 3, "total_rounds": 3}`.

## Post-reentry Recovery Remediation

- Pre-commit meta review later found that the regenerated package still
  reported `{"rounds": 2, "total_rounds": 2, "reentry": true}` while staged
  repo truth required 3/3. The dispatcher had wrapped Phase B's structured
  `post_reentry_supervisor` JSON in `stdout`, but recovery classification only
  saw the outer `phase_b` failure and fell into generic Tier 3 `needs_phase_b`.
- `recovery_gate.py` now merges embedded structured payloads for post-reentry
  `NEEDS_PHASE_B` classification and for checkpoint seeding, preserving
  `plan_path`, `bridge_rounds`, changed-file scope, and fingerprint before the
  dispatcher retry launches a fresh Phase B process.
- `phase_b_executor.py` now bounds the TASKS bridge-round scan to the current
  tracker entry, so the documented floor cannot be inflated by a later same-date
  wave while still preventing package/handoff underreporting.
- `mu/tests/tools/test_recovery_gate.py::test_post_reentry_needs_phase_b_embedded_stdout_classified_as_tier1_resume`
  locks the embedded-JSON recovery path.
- `mu/tests/tools/test_phase_b_executor.py::test_packet_documented_bridge_round_floor_bounds_tasks_scan_to_current_entry`
  locks the bounded TASKS scan.

## Post-reentry Deferred Packet Remediation

- Bridge review found that `fix_post_reentry_needs_phase_b()` merged embedded
  post-reentry supervisor payloads for plan path, bridge rounds, scope,
  non-blocking finding state, and fingerprint, but still read
  `deferred_packet_path` from the outer executor wrapper.
- `recovery_gate.py` now reads `deferred_packet_path` from the merged
  `result_payload`, so deferred non-blocking packet acknowledgement survives
  dispatcher-wrapped `stdout` payloads during deterministic Phase B re-entry
  checkpoint seeding.
- `mu/tests/tools/test_recovery_gate.py::test_post_reentry_needs_phase_b_embedded_stdout_classified_as_tier1_resume`
  now includes an embedded-only `deferred_packet_path` and asserts it is written
  to `.agent_bus/executors/phase_b_state.json`.

## Post-commit Continuation Remediation

- Bridge review found that Step 5c refreshed the in-memory handoff and recomputed
  `handoff_sha` before Step 9 wrote the post-commit continuation record. CLI
  reruns reload the original `--handoff` file, so the continuation lookup could
  miss and re-enter pre-commit Steps 3-10 after a local commit.
- `commit_executor.py` now treats `handoff_sha` as the immutable continuation key
  for the caller-supplied handoff and records the rebuilt supervisor handoff hash
  separately as `refreshed_handoff_sha`.
- `mu/tests/tools/test_commit_executor_receipt.py::test_commit_packet_truth_refresh_keeps_continuation_bound_to_original_handoff`
  reproduces the two-run shape: first run refreshes packet truth and writes the
  continuation, second run uses the original handoff and resumes post-commit.

## Phase B Local Validation

- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py -k 'packet or truth or handoff or tracker'` - 30 passed, 29 deselected.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py` - 58 passed.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_dispatch.py -k 'handoff or tracker or commit'` - 145 passed, 253 deselected.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_phase_b_executor.py -k 'handoff or packet or tracker'` - 64 passed, 241 deselected.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_recovery_gate.py -k 'post_reentry_needs_phase_b'` - 2 passed, 940 deselected.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_recovery_gate.py -k 'pane_timeline_shows_last_pager_wake_summary'` - 1 passed, 941 deselected.
- `bash tools/checks/check_stale_next_items.sh` - checked 9 PR references in NEXT; all NEXT items with merged PRs are properly marked.
- `./tools/checks/check_docs_consistency.sh` - all checks passed; docs are consistent.

## Residual Risks

- This wave deliberately does not solve the separate stale Phase B reviewer
  state reconciliation follow-on still recorded under `[PIPELINE-AGENT-PAGER]`.
- The commit executor still regenerates the L4 indicator during the real commit
  path; the Phase B artifact in `reports/l4_wave_indicators/` is the local
  range-based proof artifact for this implementation packet.
- Pane 4 is a display surface only; this wave keeps pager/autoping observability
  visible but does not make pane text authoritative for packet or commit truth.

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pager-commit-packet-truth-refresh-2026-04-28`
- Active packet: `reports/control_plane/pager_commit_packet_truth_refresh_2026-04-28.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `3d62d5cae3e804e29c0dacfddd96801bcde03536bdcf0498e116b5d79487c0e8`
- Indicator artifact: `reports/l4_wave_indicators/pager-commit-packet-truth-refresh-2026-04-28.json`
- Pre-commit receipt handle: `.agent_bus/meta/pre_commit_receipts/receipt_2026-04-28T21-57-28p00-00_88dc0f2a.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_receipt.py mu/tests/tools/test_executor_dispatch.py mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_recovery_gate.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pager_commit_packet_truth_refresh_2026-04-28.md. (2) Final pytest gate covered 4 test file(s) from the wave-owned diff. (3) Commit handoff carries explicit receipt authority at .agent_bus/meta/pre_commit_receipts/receipt_2026-04-28T21-57-28p00-00_88dc0f2a.json..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pager-commit-packet-truth-refresh-2026-04-28.json`
  - `pre_commit_receipt`: `.agent_bus/meta/pre_commit_receipts/receipt_2026-04-28T21-57-28p00-00_88dc0f2a.json`
- Current staged files:
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/pager_commit_packet_truth_refresh_2026-04-28.md`
  - `reports/l4_wave_indicators/pager-commit-packet-truth-refresh-2026-04-28.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
