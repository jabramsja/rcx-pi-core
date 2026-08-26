# PR 1219 P0IBRRCP Receipt Authority R1 2026-08-26

Date: 2026-08-26
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [ROLES-ALL-CODEX-PR1219-P0IBRRCP-RECEIPT-AUTHORITY-R1]
Wave ID: pr1219-p0ibrrcp-receipt-authority-r1-2026-08-26
Phase-A-Lock: LOCKED
Purpose: Land the narrow receipt-authority prerequisite requested by the stopped provider-neutral R2 review: validate the complete supervisor response on every receipt-minting entry path and at the writer authority boundary before any commit authority is minted, and revoke older canonical COMMIT_GO authority before attempting a new exact receipt so an exact-receipt write failure cannot preserve stale commit authority, without changing later client path conversion, bridge job recovery, routing, commit execution, runtime, substrate, seed, or Mu behavior.

## Scope

From exact PR 1246 merge authority, close only the two coupled receipt-issuance failures recorded in the canonical TASKS entry: a commit-capable response missing a required field can mint exact and canonical receipts before client validation rejects it, and an exact-receipt write failure can leave older canonical COMMIT_GO authority valid. Validate required response fields before writing receipts through either the client wrapper or the supervisor's independent direct path, enforce the same contract at the receipt writer boundary, invalidate older canonical authority before starting the exact-receipt write, and update focused tests plus narrow TASKS/preservation truth. Client-side `git rev-parse` and `Path.relative_to` rollback and cleanup of a newly created exact receipt after a later canonical-publication failure are not authorized pending work in this packet.

Files and surfaces in scope:

- mu/tools/agents/meta_bridge_client.py (MODIFY) -- validate presence and non-null values for decision, summary, and status immediately after run_meta_bridge returns, before decision validation or any receipt-capable branch calls write_pre_commit_receipt; preserve valid response construction, repo-relative handoff, retry, optional-field behavior, and the existing later path-conversion flow.
- mu/tools/agents/meta_bridge_supervisor.py (MODIFY) -- enforce the same complete required-response contract before main's independent receipt-writer call and again at the write_pre_commit_receipt authority boundary so direct callers cannot mint from a malformed response; after validation, invalidate any existing canonical receipt before beginning the exact-receipt write so failure of that write cannot preserve older canonical authority.
- mu/tests/tools/test_meta_bridge_client.py (MODIFY) -- prove missing or null required fields on a commit-capable response raise MetaBridgeClientError before write_pre_commit_receipt is called and create no receipt authority.
- mu/tests/tools/test_meta_bridge_supervisor.py (MODIFY) -- prove the supervisor main/direct-writer path and the writer boundary reject malformed commit-capable responses before receipt side effects, and strengthen the exact-write-failure regression by pre-seeding older canonical COMMIT_GO authority and proving the failed new issuance revokes it.
- TASKS.md (MODIFY) -- record PR 1246 merge truth; preserve provider-neutral R1 and R2 identities and exact stop/no-push evidence; record this receipt prerequisite as current, hybrid-review terminality as the next prerequisite, provider-neutral reconstruction after both, and normal-exit cleanup as the unchanged sole numbered immediate NEXT functional row; retain every task, preservation record, and all five TODO-bearing lines byte-for-byte.
- reports/control_plane/pr1219-p0ibrrcp-receipt-authority-r1-2026-08-26_2026-08-26.md (GENERATED) -- sole canonical same-wave packet.
- reports/l4_wave_indicators/pr1219-p0ibrrcp-receipt-authority-r1-2026-08-26.json (PHASE B GENERATED GOVERNANCE) -- same-wave indicator collected and staged before review.
- reports/deferred/non_blocking/pr1219-p0ibrrcp-receipt-authority-r1-2026-08-26_bridge_nonblockers.md (GENERATED ONLY IF NEEDED) -- same-wave nonblocking findings only.
- TASKS.md -- tracker-sync authority. The 2026-08-26 tracker sync note for wave `pr1219-p0ibrrcp-receipt-authority-r1-2026-08-26` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/pr1219-p0ibrrcp-receipt-authority-r1-2026-08-26_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Reconstruct only from exact merge 15abb77b7b48688fd118363e5d517ec3c4813afc. Do not resume, copy, mutate, stage, or source any stopped provider-neutral target, packet, bus, branch, or candidate file.
2. Move complete required-field validation ahead of _validate_decision and the receipt-capable branch in run_meta_bridge_package; add the same presence-and-non-null validation for decision, summary, and status in meta_bridge_supervisor.main before its independent writer call and at the beginning of write_pre_commit_receipt before decision-capability, staged-state, directory, invalidation, or write work. Malformed client responses must raise MetaBridgeClientError without calling the writer, and malformed supervisor/direct-writer responses must fail closed without creating exact or canonical authority.
3. After complete-response validation succeeds, invalidate existing canonical receipt authority before attempting the new exact-receipt write. If that exact write fails, propagate the existing failure only after the older canonical receipt has been removed or made non-authorizing. Do not extend this work into client portability conversion or post-exact canonical-publication rollback.
4. Add focused negative controls for an already-valid canonical receipt plus forced exact-write failure. Prove default canonical verification rejects after the exception. Also add parameterized missing-or-null decision, summary, and status through run_meta_bridge_package with a mocked writer that must remain uncalled; reproduce the supervisor main/direct-writer path with an explicit null summary, proving its writer remains uncalled and neither exact nor canonical authority is created; and exercise the writer guard directly so bypassing either higher-level entry-point check still fails before staged-SHA or receipt filesystem side effects.
5. Refresh TASKS without adding or renumbering PROGRAM QUEUE rows: record stopped R2 precisely, make this unnumbered prerequisite current, keep hybrid terminality next, retain the provider-neutral reconstruction and numbered normal-exit sequence, and preserve all five TODO-bearing lines.
6. Complete launch_wave.py dispatcher, Phase A, Phase B, providerless terminal executor, PR checks, Codex review clearance, and merge through the normal immutable-source pipeline.

## Constraints

- Functional scope is exactly meta_bridge_client.py, meta_bridge_supervisor.py, test_meta_bridge_client.py, test_meta_bridge_supervisor.py, TASKS, and same-wave generated governance. test_pre_commit_receipt.py is validation-only and must not change.
- Do not change bridge_supervisor.py hybrid job state in this receipt packet. The separately queued hybrid-review terminality prerequisite owns the executable-reader recovery blocker and is non-blocking for this receipt transaction unless an existing declared receipt test proves direct coupling.
- Do not change receipt-capable decisions, receipt schema, staged-SHA binding, max age, package digest, exact-path return contract, canonical hook location, commit executor behavior, routing, recovery, bridge adapters, runtime, substrate, seed, host semantics, or Mu semantics.
- Preserve successful issuance behavior and explicit receipt_path verification semantics. Do not sweep historical exact receipts or weaken verify_pre_commit_receipt by ignoring an explicit path.
- Preserve the existing fail-closed repo-relative handoff. Do not change, weaken, or skip `git rev-parse`/`Path.relative_to`, add rollback around those client conversion steps, or return an absolute receipt path in this packet.
- Do not add cleanup for a newly created exact receipt after canonical publication or another later issuance step fails; TASKS does not authorize that post-exact rollback regression in this wave.
- Do not coerce an absent or explicit null required field to an empty/default value; preserve valid response construction, but reject malformed responses at each receipt entry point and at the writer boundary.
- Do not fix filename-collision, timestamp-format, latest-negative-decision revocation policy, direct-review identity validation, stale prose, or any other deferred/non-occurring edge case in this packet.
- Do not edit Claude-owned files or treat provider-local memory as candidate evidence. Do not remove Claude or Fable as available provider-menu choices.
- Use launch_wave.py and the immutable-source pipeline only. No manual candidate patch, staging, commit, push, PR, merge, source substitution, or preserved-lane folding.
- Every model-bearing implementation, review, meta-review, pager, bot-remediation, and recovery role is Codex. Commit execution remains providerless.

## Stop conditions

- Stop before launch if source HEAD, target HEAD, origin/dev, or comparison_commit differs from 15abb77b7b48688fd118363e5d517ec3c4813afc; if source or target is dirty; if identity collides; if the dated packet stem exceeds the 80-character Phase A bound; or if Codex implementer, reviewer, and pager pins or providerless commit are unavailable.
- Stop and preserve if any canonical or routed packet path differs from reports/control_plane/pr1219-p0ibrrcp-receipt-authority-r1-2026-08-26_2026-08-26.md or if a second packet alias appears.
- Stop and preserve if a real failing declared receipt gate proves bridge job recovery, commit execution, runtime, substrate, seed, Mu, or another functional file outside the allowlist must change; create the separately queued prerequisite rather than widening this candidate.
- Stop and preserve if the two TASKS-recorded failures cannot be closed within meta_bridge_client.py, meta_bridge_supervisor.py, and their two focused test files; do not add client portability rollback or post-exact canonical-publication cleanup to avoid a bounded reconstruction.
- Do not stop, widen, or remediate for the separately queued hybrid-review recovery defect, receipt filename collisions, naive timestamps, later-negative-decision policy, unused direct APIs, spelling, stale prose, or any non-occurring nonblocker.
- If review does not converge, preserve the exact candidate and launch a bounded replacement through launch_wave.py; never recursively relaunch or mutate the stopped lane.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_meta_bridge_client.py mu/tests/tools/test_meta_bridge_supervisor.py`
- direct_entry_path_command: `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 python3 -m pytest -x --tb=short -p no:cacheprovider mu/tests/tools/test_meta_bridge_client.py mu/tests/tools/test_meta_bridge_supervisor.py`

## Acceptance criteria

- Only the eight allowlisted candidate paths change; the optional nonblocker is absent unless needed; exactly one canonical packet exists and no truncated or alternate alias is created.
- Launch metadata proves implementer_agent=codex, reviewer_agent=codex, pager_route=codex, exact comparison commit, collision-free packet identity, and providerless commit execution.
- A response with an absent or null decision, summary, or status is rejected before receipt minting on every entry path: run_meta_bridge_package raises MetaBridgeClientError without calling its writer, meta_bridge_supervisor.main rejects the malformed response before its independent writer call, and write_pre_commit_receipt independently rejects any caller that bypasses either entry-point check before staged-SHA or receipt filesystem side effects.
- Before a new exact-receipt write is attempted, older canonical COMMIT_GO authority is absent or non-authorizing. If the exact write fails, verify_pre_commit_receipt rejects the default canonical path for the current staged state; no acceptance claim is made here about cleanup after a later canonical-publication or client path-conversion failure.
- The exact four-selector evidence command recorded in TASKS passes, together with the client malformed-response regression, supervisor main/direct-writer malformed-response regressions, writer-boundary negative control, older-canonical revocation regression, full changed test files, staged L4 enforcement, pre-push-fast, and required CI.
- TASKS records PR 1246 and stopped provider-neutral R1/R2 truth, retains every queued task and preservation record, leaves normal-exit cleanup as the sole numbered immediate NEXT functional row after the prerequisite chain, preserves P0R2 as open after P0T4, and contains exactly the existing five TODO-bearing lines.
- Launch evidence proves required CI, fresh Codex review clearance, providerless terminal execution, and normal merge completion.

## Grounding / Authorization

- Task: [ROLES-ALL-CODEX-PR1219-P0IBRRCP-RECEIPT-AUTHORITY-R1]; wave id `pr1219-p0ibrrcp-receipt-authority-r1-2026-08-26`.
- Governing packet: this file, `reports/control_plane/pr1219-p0ibrrcp-receipt-authority-r1-2026-08-26_2026-08-26.md`.
- TASKS.md authority: the 2026-08-26 tracker sync note for wave `pr1219-p0ibrrcp-receipt-authority-r1-2026-08-26` authorizes exactly the two reproduced failures stated above, complete-response validation before receipt creation, fail-closed canonical invalidation across exact-receipt write failure, and the four-selector evidence command reproduced verbatim in this packet; it is canonical for this packet's L4 fields.
- Reviewer correction authority: the current bridge REQUEST_CHANGES finding establishes that the prior packet exceeded canonical TASKS authority by adding `git rev-parse` rollback, `Path.relative_to` rollback, a post-exact canonical-write rollback regression, and three additional focused selectors. This rewrite removes those items from pending work, validation, and acceptance rather than treating them as authorized unresolved work.
- Authorization: The founder requires every model-bearing role to use Codex, every candidate to enter through launch_wave.py, TASKS and TODO truth to remain synchronized, stopped evidence never to be lost, and active landing convergence to take priority over unrelated edge cases. The stopped R2 reviewer explicitly requested one narrower receipt-authority prerequisite for these two coupled blockers; no deferred finding is authorized here.

FOUNDER_OVERRIDE:pr1219-p0ibrrcp-receipt-authority-r1-2026-08-26

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `pr1219-p0ibrrcp-receipt-authority-r1-2026-08-26`
- Active packet: `reports/control_plane/pr1219-p0ibrrcp-receipt-authority-r1-2026-08-26_2026-08-26.md`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrcp-receipt-authority-r1-2026-08-26.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_meta_bridge_client.py`
  - `mu/tests/tools/test_meta_bridge_supervisor.py`
  - `mu/tools/agents/meta_bridge_client.py`
  - `mu/tools/agents/meta_bridge_supervisor.py`
  - `reports/control_plane/pr1219-p0ibrrcp-receipt-authority-r1-2026-08-26_2026-08-26.md`
  - `reports/deferred/non_blocking/pr1219-p0ibrrcp-receipt-authority-r1-2026-08-26_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrcp-receipt-authority-r1-2026-08-26.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `pr1219-p0ibrrcp-receipt-authority-r1-2026-08-26`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/pr1219-p0ibrrcp-receipt-authority-r1-2026-08-26_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pr1219-p0ibrrcp-receipt-authority-r1-2026-08-26.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr1219-p0ibrrcp-receipt-authority-r1-2026-08-26 --output reports/l4_wave_indicators/pr1219-p0ibrrcp-receipt-authority-r1-2026-08-26.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_meta_bridge_client.py mu/tests/tools/test_meta_bridge_supervisor.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrcp-receipt-authority-r1-2026-08-26_2026-08-26.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_meta_bridge_client.py`, `mu/tests/tools/test_meta_bridge_supervisor.py`, `mu/tools/agents/meta_bridge_client.py`, `mu/tools/agents/meta_bridge_supervisor.py`, `reports/control_plane/pr1219-p0ibrrcp-receipt-authority-r1-2026-08-26_2026-08-26.md`, `reports/deferred/non_blocking/pr1219-p0ibrrcp-receipt-authority-r1-2026-08-26_bridge_nonblockers.md`, `reports/l4_wave_indicators/pr1219-p0ibrrcp-receipt-authority-r1-2026-08-26.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pr1219-p0ibrrcp-receipt-authority-r1-2026-08-26.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pr1219-p0ibrrcp-receipt-authority-r1-2026-08-26`
- Active packet: `reports/control_plane/pr1219-p0ibrrcp-receipt-authority-r1-2026-08-26_2026-08-26.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `872ecbf3eb8a2205544eb95aa081940abfce3435567aa336589d81ce447a529c`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrcp-receipt-authority-r1-2026-08-26.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_meta_bridge_client.py mu/tests/tools/test_meta_bridge_supervisor.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrcp-receipt-authority-r1-2026-08-26_2026-08-26.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_meta_bridge_client.py`, `mu/tests/tools/test_meta_bridge_supervisor.py`, `mu/tools/agents/meta_bridge_client.py`, `mu/tools/agents/meta_bridge_supervisor.py`, `reports/control_plane/pr1219-p0ibrrcp-receipt-authority-r1-2026-08-26_2026-08-26.md`, `reports/deferred/non_blocking/pr1219-p0ibrrcp-receipt-authority-r1-2026-08-26_bridge_nonblockers.md`, `reports/l4_wave_indicators/pr1219-p0ibrrcp-receipt-authority-r1-2026-08-26.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pr1219-p0ibrrcp-receipt-authority-r1-2026-08-26.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_meta_bridge_client.py`
  - `mu/tests/tools/test_meta_bridge_supervisor.py`
  - `mu/tools/agents/meta_bridge_client.py`
  - `mu/tools/agents/meta_bridge_supervisor.py`
  - `reports/control_plane/pr1219-p0ibrrcp-receipt-authority-r1-2026-08-26_2026-08-26.md`
  - `reports/deferred/non_blocking/pr1219-p0ibrrcp-receipt-authority-r1-2026-08-26_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrcp-receipt-authority-r1-2026-08-26.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
