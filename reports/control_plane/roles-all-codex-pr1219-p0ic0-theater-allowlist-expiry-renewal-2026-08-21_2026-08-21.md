# PR 1219 P0IC0 Theater Allowlist Expiry Renewal 2026-08-21

Date: 2026-08-21
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [ROLES-ALL-CODEX-PR1219-P0IC0-THEATER-ALLOWLIST-EXPIRY-RENEWAL]
Wave ID: roles-all-codex-pr1219-p0ic0-theater-allowlist-expiry-renewal-2026-08-21
Phase-A-Lock: LOCKED
Purpose: Unblock every queued wave after P0IC1 reproduced a dev-wide pre-push failure: renew only the expiry date on the nine unchanged founder-owned heuristic_false_positive theater-risk entries, without adding findings, changing classifications, modifying the classifier, or absorbing any PR1219 implementation scope.

## Scope

Fresh P0IC0 lane at origin/dev commit 019bf08444390dcf875a6941f72fdb68f1e5fad3, whose authoritative nine-entry mu/tools/checks/theater_allowlist.json has SHA-256 79766cfa2f82c5a6a23eb8921c2181b7f201ec5806801269ed5f3fd3773ca109. Exact implementation scope is nine expires_on value changes in that file plus TASKS and generated same-wave governance only.

Files and surfaces in scope:

- mu/tools/checks/theater_allowlist.json (MODIFY) -- change exactly nine expires_on values from 2026-08-02 to 2026-09-20; preserve entry count, order, identity, classification, reason, owner, and target wave.
- TASKS.md (MODIFY THROUGH PIPELINE) -- reproduce the checksummed 56-row P0IC0 -> P0IC1 -> P0IC2 -> P0IA queue while preserving every prior task ID, order, TODO disposition, and generated same-wave tracker note.
- reports/control_plane/roles-all-codex-pr1219-p0ic0-theater-allowlist-expiry-renewal-2026-08-21_2026-08-21.md (GENERATED) -- governing same-wave packet.
- reports/l4_wave_indicators/roles-all-codex-pr1219-p0ic0-theater-allowlist-expiry-renewal-2026-08-21.json (GENERATED) -- same-wave indicator.
- reports/deferred/non_blocking/roles-all-codex-pr1219-p0ic0-theater-allowlist-expiry-renewal-2026-08-21_bridge_nonblockers.md (GENERATED ONLY IF NEEDED) -- exact same-wave reviewer deferrals; nonblockers cannot widen or delay P0IC0.
- TASKS.md -- tracker-sync authority. The 2026-08-21 tracker sync note for wave `roles-all-codex-pr1219-p0ic0-theater-allowlist-expiry-renewal-2026-08-21` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Load the current allowlist and prove before editing that its SHA-256 is 79766cfa2f82c5a6a23eb8921c2181b7f201ec5806801269ed5f3fd3773ca109, it has exactly nine entries, all owner=founder, all classification=heuristic_false_positive, all target_wave=A18-P1, all expires_on=2026-08-02, and that the UTC ratchet reports current_count=9, allowlist_count=9, expired=9, and empty new/real/removals.
2. Change only each existing entry's expires_on value to 2026-09-20. Do not reorder, normalize, add, remove, or rewrite any other byte or field.
3. Prove after editing that the file SHA-256 is exactly 9676fb46c756125275e03d3c62856e907859ffa54609575f422d8f7c592ab4fa, the before/after entry identity tuples and all non-expiry fields are identical, exactly nine expiry values changed, and UTC ratchet output has current_count=9, allowlist_count=9, passed=true, and empty new/expired/real/removals.
4. Reconcile TASKS.md through the implementer from /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX-preservation/pr1219-p0ic0-queue-ready-20260821/TASKS.md, SHA-256 dfdb29ecc1ba21a0b0a699aacb9709be422bce729b454df656160b25aa95bec0, preserving the generated P0IC0 tracker note.
5. Run implementation, review, pager, staging, providerless commit, push, PR, CI, and merge through the normal all-Codex pipeline.

## Constraints

- The only starting commit is origin/dev 019bf08444390dcf875a6941f72fdb68f1e5fad3 in a fresh unique P0IC0 worktree and bus.
- The exact candidate scope contains only TASKS.md; mu/tools/checks/theater_allowlist.json; the same-wave generated packet; the same-wave indicator; and, only if produced, the exact same-wave deferred nonblocker report. The root WaveConfig and preservation snapshot are external launch inputs and never candidate content.
- This is an expiry renewal, not allowlist expansion: add no entry, remove no entry, change no identity or classification, and do not touch check_gate_behavioral_pairs.py, check_theater_risk_ratchet.py, any test, runtime, substrate, role/model, launch, Phase A/B, commit, recovery, or bridge file.
- Do not absorb P0IC1, P0IC2, P0IA, the separate A18-P1 behavioral/classifier adjudication, or any deferred edge case. Nonblocking findings cannot delay the dev-wide unblocker.
- Preserve [THEATER-RATCHET-EXPIRY-POLICY] as POLICY_BOUND: this temporary same-entry renewal neither changes the hard-failure policy nor claims permanent expiry-semantics closure.
- P0IC0 is a pre-P0IA bootstrap packet and shares only the declared bounded pre-P0IA review-authority waiver. It waives no implementation review, exact scope, theater checks, staged L4, providerless commit, CI, or merge gate.
- All model-bearing roles remain Codex and commit remains providerless. No review, exact-scope, ratchet, staged L4, CI, or merge gate is waived.

## Stop conditions

- Halt before launch if origin/dev is not 019bf08444390dcf875a6941f72fdb68f1e5fad3, the lane or bus is not fresh and unique, any model-bearing role is not Codex, or commit execution is provider-backed.
- Halt as NEEDS_RESCOPING if the base allowlist SHA-256 is not 79766cfa2f82c5a6a23eb8921c2181b7f201ec5806801269ed5f3fd3773ca109, current_count or allowlist_count is not 9, any new/real/removal finding exists, any entry is not founder-owned heuristic_false_positive target_wave A18-P1, or any non-expiry allowlist byte must change.
- Halt rather than extending the date beyond 2026-09-20 or modifying classifier/test behavior. Do not refresh P0IC1 until exact P0IC0 PR and merge SHA evidence exists.

## Validation gates

- evidence_command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id roles-all-codex-pr1219-p0ic0-theater-allowlist-expiry-renewal-2026-08-21 --output reports/l4_wave_indicators/roles-all-codex-pr1219-p0ic0-theater-allowlist-expiry-renewal-2026-08-21.json`

## Acceptance criteria

- The staged allowlist diff is exactly nine expires_on replacements from 2026-08-02 to 2026-09-20 and no other allowlist change; the resulting file SHA-256 is 9676fb46c756125275e03d3c62856e907859ffa54609575f422d8f7c592ab4fa.
- UTC ratchet output reports current_count=9, allowlist_count=9, passed=true, and empty new, expired, real, and removals.
- The final candidate contains no classifier, test, runtime, substrate, role/model, launch, review, commit, recovery, or bridge change.
- TASKS retains all prior 55 ordered queue identities and adds only P0IC0 at position 0, yielding one unique contiguous 0..55 queue.
- Staged L4 contract, independent review, providerless commit, pre-push, CI, and deterministic merge are green.

## Grounding / Authorization

- Task: [ROLES-ALL-CODEX-PR1219-P0IC0-THEATER-ALLOWLIST-EXPIRY-RENEWAL]; wave id `roles-all-codex-pr1219-p0ic0-theater-allowlist-expiry-renewal-2026-08-21`.
- Governing packet: this file, `reports/control_plane/roles-all-codex-pr1219-p0ic0-theater-allowlist-expiry-renewal-2026-08-21_2026-08-21.md`.
- TASKS.md authority: the 2026-08-21 tracker sync note for wave `roles-all-codex-pr1219-p0ic0-theater-allowlist-expiry-renewal-2026-08-21` is canonical for this packet's L4 fields.
- Authorization: Founder directed autonomous use of narrower packets when active blockers prevent convergence and directed that landing blockers, rather than edge cases or nonblockers, be resolved so the waves land. This authorizes only the same-entry bounded expiry renewal described here; it does not authorize allowlist entry expansion or classification changes.

FOUNDER_OVERRIDE:roles-all-codex-pr1219-p0ic0-theater-allowlist-expiry-renewal-2026-08-21

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `roles-all-codex-pr1219-p0ic0-theater-allowlist-expiry-renewal-2026-08-21`
- Active packet: `reports/control_plane/roles-all-codex-pr1219-p0ic0-theater-allowlist-expiry-renewal-2026-08-21_2026-08-21.md`
- Indicator artifact: `reports/l4_wave_indicators/roles-all-codex-pr1219-p0ic0-theater-allowlist-expiry-renewal-2026-08-21.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tools/checks/theater_allowlist.json`
  - `reports/control_plane/roles-all-codex-pr1219-p0ic0-theater-allowlist-expiry-renewal-2026-08-21_2026-08-21.md`
  - `reports/l4_wave_indicators/roles-all-codex-pr1219-p0ic0-theater-allowlist-expiry-renewal-2026-08-21.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/roles-all-codex-pr1219-p0ic0-theater-allowlist-expiry-renewal-2026-08-21.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id roles-all-codex-pr1219-p0ic0-theater-allowlist-expiry-renewal-2026-08-21 --output reports/l4_wave_indicators/roles-all-codex-pr1219-p0ic0-theater-allowlist-expiry-renewal-2026-08-21.json.
- `target_gate_id`: G8.
- `evidence_command`: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id roles-all-codex-pr1219-p0ic0-theater-allowlist-expiry-renewal-2026-08-21 --output reports/l4_wave_indicators/roles-all-codex-pr1219-p0ic0-theater-allowlist-expiry-renewal-2026-08-21.json`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/roles-all-codex-pr1219-p0ic0-theater-allowlist-expiry-renewal-2026-08-21_2026-08-21.md. (2) Commit handoff carries 4 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface. scope_refs: `TASKS.md`, `mu/tools/checks/theater_allowlist.json`, `reports/control_plane/roles-all-codex-pr1219-p0ic0-theater-allowlist-expiry-renewal-2026-08-21_2026-08-21.md`, `reports/l4_wave_indicators/roles-all-codex-pr1219-p0ic0-theater-allowlist-expiry-renewal-2026-08-21.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: roles-all-codex-pr1219-p0ic0-theater-allowlist-expiry-renewal-2026-08-21.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `roles-all-codex-pr1219-p0ic0-theater-allowlist-expiry-renewal-2026-08-21`
- Active packet: `reports/control_plane/roles-all-codex-pr1219-p0ic0-theater-allowlist-expiry-renewal-2026-08-21_2026-08-21.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `7ce09ec2bf95ffa2075256f29cdb17b54b5652df907e663e84f42ce99c28b171`
- Indicator artifact: `reports/l4_wave_indicators/roles-all-codex-pr1219-p0ic0-theater-allowlist-expiry-renewal-2026-08-21.json`
- Evidence command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id roles-all-codex-pr1219-p0ic0-theater-allowlist-expiry-renewal-2026-08-21 --output reports/l4_wave_indicators/roles-all-codex-pr1219-p0ic0-theater-allowlist-expiry-renewal-2026-08-21.json`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/roles-all-codex-pr1219-p0ic0-theater-allowlist-expiry-renewal-2026-08-21_2026-08-21.md. (2) Commit handoff carries 4 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface. scope_refs: `TASKS.md`, `mu/tools/checks/theater_allowlist.json`, `reports/control_plane/roles-all-codex-pr1219-p0ic0-theater-allowlist-expiry-renewal-2026-08-21_2026-08-21.md`, `reports/l4_wave_indicators/roles-all-codex-pr1219-p0ic0-theater-allowlist-expiry-renewal-2026-08-21.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/roles-all-codex-pr1219-p0ic0-theater-allowlist-expiry-renewal-2026-08-21.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tools/checks/theater_allowlist.json`
  - `reports/control_plane/roles-all-codex-pr1219-p0ic0-theater-allowlist-expiry-renewal-2026-08-21_2026-08-21.md`
  - `reports/l4_wave_indicators/roles-all-codex-pr1219-p0ic0-theater-allowlist-expiry-renewal-2026-08-21.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
