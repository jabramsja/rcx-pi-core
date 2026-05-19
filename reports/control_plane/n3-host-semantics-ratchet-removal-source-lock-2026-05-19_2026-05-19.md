# N3-Host-Semantics-Ratchet-Removal-Source-Lock-2026-05-19

Date: 2026-05-19
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-host-semantics-ratchet-removal-source-lock-2026-05-19
Class: L4_ENABLER
Category: /mu structural host-semantics ratchet source-lock
Target gate: G8
Phase-A-Lock: LOCKED
Purpose: Contract active: founder XML + repo protocol in force.

## Scope

This packet locks one bounded Phase A source-lock after PR #991 and the bridge
REQUEST_CHANGES review. It does not authorize direct Phase B implementation in
this rewrite turn. The committed package now satisfies the detector-visible
tracker gate: `TASKS.md:381` names this exact wave id and packet path, so
downstream structural review must not treat tracker absence as blocking.

Selected next slice: Stage0 match/substitute host-semantics marker reduction.

In scope for this rewrite turn:
- Control packet only:
  `reports/control_plane/n3-host-semantics-ratchet-removal-source-lock-2026-05-19_2026-05-19.md`.

Current source-lock evidence for the selected downstream slice:
- Python Stage0 match/substitute marker slice:
  `mu/host/python/rcx_pi/selfhost/eval_seed.py:524-533` and
  `mu/host/python/rcx_pi/selfhost/eval_seed.py:603-609`.
- JavaScript Stage0 match/substitute parity marker slice:
  `mu/host/js/core/bootstrap_core.js:443` and
  `mu/host/js/core/bootstrap_core.js:517`.

Explicitly excluded from the selected slice:
- `mu/host/js/core/bootstrap_core.js:293`, which is the projection-loop
  `@host_iteration` marker for first-match-wins projection dispatch, not a
  Stage0 match/substitute marker.
- Any other marker, file, directory, or broad host-semantics inventory not
  listed in the selected downstream slice above.

Candidate downstream implementation scope, with the detector-visible TASKS
tracker condition satisfied by `TASKS.md:381` and only if Phase B proves the
selected slice is removable or structurally reducible:
- Selected Python implementation lines in
  `mu/host/python/rcx_pi/selfhost/eval_seed.py`.
- Selected JavaScript implementation lines in
  `mu/host/js/core/bootstrap_core.js`.
- Focused proof may add or update only selected-boundary tests under
  `mu/tests/parity/` and `mu/tests/l4_gates/`.
- Required validation surfaces are read-only except for normal command output:
  `mu/tools/checks/check_host_semantics_ratchet.py`,
  `tools/checks/check_host_authority_inventory_ratchet.py`,
  `tools/checks/enforce_l4_execution_contract.py`,
  `tools/metrics/collect_l4_wave_indicators.py`, and
  `tools/checks/check_docs_consistency.sh`.

- `reports/deferred/non_blocking/n3-host-semantics-ratchet-removal-source-lock-2026-05-19_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work Items

Contract active: founder XML + repo protocol in force.

Autonomous founder instruction is active: continue non-interactively through
pipeline waves, use builders/receipt/commit surfaces first, and stop only for
an explicit founder question. This wave must program in Mu and narrow/remove
host semantics rather than adding Python/JavaScript host semantics.

Concrete bounded tasks for this Phase A packet:
1. Lock this separate bounded control-plane packet for the still-open
   `[NEXT-CODEX-POST-REDTEAM]` current phase. `TASKS.md:557-560` authorizes
   only future bounded work not already proven by landed slices, so this packet
   must not replay the landed engine-state/scheduler slice or use old
   control-surface packets as substantive closure evidence.
2. Record the current tracker gate honestly. `TASKS.md:381` contains the
   detector-visible same-wave tracker entry for this exact wave id and packet
   path, satisfying the bounded-packet-plus-tracker requirement cited by
   `reports/control_plane/post_redteam_structural_queue_2026-03-20.md:110-113`.
   Any remaining Phase B hold must come from selected-slice proof, validation,
   or scope failure, not from a missing TASKS tracker entry.
3. Select exactly one next marker slice. This packet selects only the Stage0
   match/substitute slice spanning the Python `eval_seed.py` markers and the
   JavaScript `bootstrap_core.js:443` and `bootstrap_core.js:517` Stage0
   markers listed in Scope.
4. Exclude `mu/host/js/core/bootstrap_core.js:293` from the selected work set
   because current code identifies it as the projection-loop
   `@host_iteration` marker, not Stage0 match/substitute work.
5. In a later Phase B implementation attempt, re-open only the selected slice
   lines and classify each selected marker as one of:
   removable-now, structurally-reducible-with-prerequisite, or irreducible
   bootstrap primitive. Line numbers are starting evidence from this packet and
   must be re-verified before editing because code can move.
6. If at least one selected marker is removable or structurally reducible,
   implement the smallest parity-preserving reduction that decreases selected
   `@host_*` reliance without adding host exception tables, Python/JavaScript
   semantic inference, smarter host behavior, or ratchet-baseline edits.
7. If no selected marker can honestly be removed or structurally reduced in
   the later Phase B wave, return NO-GO with the precise prerequisite packet
   needed next and do not ask the founder to choose between implementation
   candidates.
8. Preserve predecessor closure. Do not relist already merged host-narrowing
   packets as unresolved: n3-projection-loader-smaller-image-production-pilot
   merged as PR #987, n3-micro-abi-public-boundary-narrowing merged as PR #988,
   and n3-engine-pipeline-run-algorithm-manifest-authority merged as PR #991.

## Constraints

- No code, test, additional TASKS, status, changelog, report index, indicator,
  commit, push, PR, or closeout edits are authorized by this packet-local
  remediation.
- The detector-visible tracker prerequisite is satisfied for this wave by
  `TASKS.md:381`; downstream Phase B authority still requires same-wave control
  authority to be mechanically derivable from that tracker entry plus this
  packet.
- Stage0 edits are in scope only for a later authorized Phase B attempt, only
  inside the selected Stage0 match/substitute lines named in Scope, and only
  while the `TASKS.md:381` tracker binding remains present.
- No edit to `mu/host/js/core/bootstrap_core.js:293` is in scope for this
  selected slice.
- No ratchet baseline update may count as proof of reduction.
- No new host exception table, Python-only semantic special case,
  JavaScript-only semantic special case, or smarter host interpretation is in
  scope.
- No scheduler, substrate, loader, binary, checksum, integrity, dispatcher,
  commit, push, PR, Claude-related, or unrelated tooling edits are in scope.
- No broad repo investigation is in scope for this packet. The evidence basis
  is intentionally limited to this packet, the exact `[NEXT-CODEX-POST-REDTEAM]`
  TASKS lines, the governing queue lines cited below, and the selected code
  lines cited in Scope.

## Stop Conditions

- Stop before any Phase B code edit if current `TASKS.md` no longer contains a
  detector-visible same-wave tracker entry for
  `n3-host-semantics-ratchet-removal-source-lock-2026-05-19` and this packet
  path.
- Stop if selected marker lines cannot be re-opened or if current code proves a
  selected work item already landed; remove that item from the pending work set
  instead of re-listing it as unresolved.
- Stop if `mu/host/js/core/bootstrap_core.js:293` appears in the selected work
  set; that marker is projection-loop dispatch and requires a separate bounded
  packet if it is ever selected.
- Stop if implementation requires touching files or directories outside the
  selected Scope.
- Stop if removal would require host exception tables, substrate-specific
  semantic inference, smarter Python/JavaScript behavior, or baseline-only
  ratchet changes.
- Stop with NO-GO if every selected marker is irreducible under the current
  architecture, and route the precise prerequisite packet needed next.
- Stop if focused parity/L4 proof, host-semantics ratchet, host-authority
  inventory ratchet, docs consistency when docs change, indicator collection,
  or strict L4 execution-contract validation fails.

## Acceptance Criteria

- This Phase A packet names a single selected next slice: Stage0
  match/substitute marker reduction across
  `mu/host/python/rcx_pi/selfhost/eval_seed.py:524-533`,
  `mu/host/python/rcx_pi/selfhost/eval_seed.py:603-609`,
  `mu/host/js/core/bootstrap_core.js:443`, and
  `mu/host/js/core/bootstrap_core.js:517`.
- This packet explicitly excludes `mu/host/js/core/bootstrap_core.js:293` from
  the selected slice.
- This packet does not claim that its packet-local `FOUNDER_OVERRIDE` is a
  detector-visible TASKS tracker entry. The detector-visible tracker entry is
  `TASKS.md:381`, which names this exact wave id and packet path; downstream
  Phase B must use that entry plus this packet as the same-wave authority
  binding.
- The in-scope downstream write surface is bounded to the selected
  implementation files and focused proof directories named in Scope.
- Downstream Phase B produces either:
  - GO: at least one selected `@host_*` marker is removed or structurally
    reduced with Python/JS parity proof, no new host semantics, no ratchet
    baseline-only proof, host-semantics ratchet passing with no increases and
    any legitimate decrease explained, host-authority inventory ratchet passing
    with no unaccepted authority increase, focused negative controls passing,
    indicator collection completed, and strict L4 execution contract passing; or
  - NO-GO: no selected marker is honestly removable or reducible, with a precise
    prerequisite packet named and no implementation edits made.
- The packet does not claim unresolved status for the landed PR #701
  engine-state/scheduler slice or for PR #987, PR #988, and PR #991.
- All founder-facing prompts and reports generated from this packet end with:
  Questions? Concerns? Thoughts? -- Think hard

## Grounding / Authorization

- Current `TASKS.md` keeps `[NEXT-CODEX-POST-REDTEAM]` UNPARKED and OPEN:
  the current phase allows only future bounded work not already proven by
  landed slices, and it explicitly says remaining structural reduction requires
  separate bounded packets.
- `TASKS.md:381` satisfies the detector-visible tracker gate for this package:
  it records the same wave id,
  `n3-host-semantics-ratchet-removal-source-lock-2026-05-19`, and this packet
  path,
  `reports/control_plane/n3-host-semantics-ratchet-removal-source-lock-2026-05-19_2026-05-19.md`.
- `TASKS.md:574` records the predecessor same-task source-lock prerequisite.
  This packet preserves that predecessor closure, does not replay it, and does
  not import the predecessor's historical implementation exclusions as the
  current selected-slice scope.
- `reports/control_plane/post_redteam_structural_queue_2026-03-20.md:110-113`
  requires a separate bounded control-plane packet and detector-visible TASKS
  tracker entry before any new structural reduction beyond listed queue state;
  it does not authorize direct unpacketed `/mu` implementation.
- Current code evidence used to correct this packet:
  `mu/host/js/core/bootstrap_core.js:293` is `@host_iteration` for projection
  dispatch, while `mu/host/js/core/bootstrap_core.js:443` and
  `mu/host/js/core/bootstrap_core.js:517` are the Stage0 recursive
  match/substitute markers. The Python selected lines still carry the Stage0
  `_stage0_match` and `_stage0_substitute` host markers at
  `mu/host/python/rcx_pi/selfhost/eval_seed.py:524-533` and
  `mu/host/python/rcx_pi/selfhost/eval_seed.py:603-609`.
- This packet satisfies the separate bounded packet portion of the queue rule,
  and `TASKS.md:381` satisfies the same-wave detector-visible tracker portion.
  The pair authorizes packetization and later review routing only; it does not
  authorize implementation during this packet-local remediation.
- FOUNDER_OVERRIDE:n3-host-semantics-ratchet-removal-source-lock-2026-05-19

Questions? Concerns? Thoughts? -- Think hard

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `n3-host-semantics-ratchet-removal-source-lock-2026-05-19`
- Active packet: `reports/control_plane/n3-host-semantics-ratchet-removal-source-lock-2026-05-19_2026-05-19.md`
- Indicator artifact: `reports/l4_wave_indicators/n3-host-semantics-ratchet-removal-source-lock-2026-05-19.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `reports/control_plane/n3-host-semantics-ratchet-removal-source-lock-2026-05-19_2026-05-19.md`
  - `reports/deferred/non_blocking/n3-host-semantics-ratchet-removal-source-lock-2026-05-19_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/n3-host-semantics-ratchet-removal-source-lock-2026-05-19.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `n3-host-semantics-ratchet-removal-source-lock-2026-05-19`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/n3-host-semantics-ratchet-removal-source-lock-2026-05-19_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `n3-host-semantics-ratchet-removal-source-lock-2026-05-19`
- Active packet: `reports/control_plane/n3-host-semantics-ratchet-removal-source-lock-2026-05-19_2026-05-19.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `1564f171c4645d68abf285285f31b1da41c336de9619ca09f93c50eed21109f1`
- Indicator artifact: `reports/l4_wave_indicators/n3-host-semantics-ratchet-removal-source-lock-2026-05-19.json`
- Evidence command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id n3-host-semantics-ratchet-removal-source-lock-2026-05-19 --output reports/l4_wave_indicators/n3-host-semantics-ratchet-removal-source-lock-2026-05-19.json`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/n3-host-semantics-ratchet-removal-source-lock-2026-05-19_2026-05-19.md. (2) Commit handoff carries 4 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/n3-host-semantics-ratchet-removal-source-lock-2026-05-19.json`
- Current staged files:
  - `TASKS.md`
  - `reports/control_plane/n3-host-semantics-ratchet-removal-source-lock-2026-05-19_2026-05-19.md`
  - `reports/deferred/non_blocking/n3-host-semantics-ratchet-removal-source-lock-2026-05-19_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/n3-host-semantics-ratchet-removal-source-lock-2026-05-19.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
