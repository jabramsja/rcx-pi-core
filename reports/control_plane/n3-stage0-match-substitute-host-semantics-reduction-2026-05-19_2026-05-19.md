# N3-Stage0-Match-Substitute-Host-Semantics-Reduction-2026-05-19

Date: 2026-05-19
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-stage0-match-substitute-host-semantics-reduction-2026-05-19
Wave Class: L4_ENABLER for packet/tracker readiness; downstream runtime edits, if authorized, become L4_STRUCTURAL.
Phase-A-Lock: LOCKED
FOUNDER_OVERRIDE:n3-stage0-match-substitute-host-semantics-reduction-2026-05-19
Purpose: Contract active: founder XML + repo protocol in force.

## Scope

Editable in this Phase A rewrite:
- `reports/control_plane/n3-stage0-match-substitute-host-semantics-reduction-2026-05-19_2026-05-19.md`

Same-wave authority scope required before Phase B:
- `TASKS.md` for one detector-visible tracker entry for `n3-stage0-match-substitute-host-semantics-reduction-2026-05-19`.

Candidate Phase B implementation scope, after same-wave tracker authority exists:
- `mu/host/python/rcx_pi/selfhost/eval_seed.py:524-533` (`_stage0_match` selected `@host_recursion` and `@host_builtin` markers).
- `mu/host/python/rcx_pi/selfhost/eval_seed.py:603-609` (`_stage0_substitute` selected `@host_recursion` marker).
- `mu/host/js/core/bootstrap_core.js:441-445` (`stage0Match` selected `@host_recursion` marker).
- `mu/host/js/core/bootstrap_core.js:515-518` (`stage0Substitute` selected `@host_recursion` marker).
- Focused Stage0/parity tests under `mu/tests/l4_gates/` and `mu/tests/parity/` only if needed to prove the selected marker classification, removal, or negative controls.
- `reports/l4_wave_indicators/n3-stage0-match-substitute-host-semantics-reduction-2026-05-19.json` for downstream indicator collection.

Evidence-only references:
- `TASKS.md:381`
- `reports/control_plane/n3-host-semantics-ratchet-removal-source-lock-2026-05-19_2026-05-19.md`
- `reports/control_plane/post_redteam_structural_queue_2026-03-20.md:110-113`

Explicitly out of scope:
- `mu/host/js/core/bootstrap_core.js:293` projection-loop dispatch.
- Any Stage0, projection, scheduler, seed, loader, pipeline, or docs edits outside the file/path list above.
- Replaying the completed predecessor source-lock packet as implementation authority.

## Work Items

1. Keep this file as the governing Phase A packet for `n3-stage0-match-substitute-host-semantics-reduction-2026-05-19`; do not create a replacement packet.
2. Before Phase B implementation, add or verify a same-wave `TASKS.md` tracker entry for this exact wave ID and packet path. `TASKS.md:381` currently records only predecessor wave `n3-host-semantics-ratchet-removal-source-lock-2026-05-19`, so predecessor tracker evidence is not sufficient Phase B authority for this successor.
3. Re-open only the selected Python and JavaScript line windows listed in Scope, then classify each selected marker as exactly one of:
   - `removable-now`
   - `structurally-reducible-with-prerequisite`
   - `irreducible-bootstrap-primitive`
4. For every marker classification, record current file:line evidence and parity implications before editing code.
5. Implement only markers classified `removable-now`, or markers classified `structurally-reducible-with-prerequisite` when the prerequisite is satisfied within this same bounded wave.
6. If no selected marker can honestly be removed or reduced in this wave, route the precise prerequisite packet and do not claim host-semantics reduction.
7. Add or update only focused Stage0/parity negative controls needed to prove the selected classification/removal. Do not add broad unrelated tests.
8. Run downstream validation: focused Stage0/parity negative controls, host-semantics ratchet, host-authority inventory ratchet, strict L4 execution contract, indicator collection, and docs consistency when docs/packets change.

## Constraints

- Program in Mu and reduce or route host-semantics markers; do not add Python or JavaScript host semantics.
- No baseline update may be used as proof.
- No host exception tables, substrate-only semantic inference, smarter host behavior, or host-oracle expansion.
- No expansion to `mu/host/js/core/bootstrap_core.js:293`.
- No unrelated Stage0, projection, scheduler, seed, loader, executor, commit, pre-commit, recovery, or pipeline edits.
- No parity-skewed implementation unless the classification evidence proves the selected marker is substrate-specific and routes that proof explicitly before implementation.
- Do not treat the completed predecessor source-lock packet as implementation authority for this successor wave.
- Do not infer that every selected marker remains unlanded from `TASKS.md`; current code line evidence must decide pending implementation scope during Phase B.

## Stop Conditions

- Stop before Phase B code edits if `TASKS.md` does not contain a detector-visible same-wave tracker entry for `n3-stage0-match-substitute-host-semantics-reduction-2026-05-19`.
- Stop if re-opened code lines differ materially from the scoped marker windows or require touching files outside the Scope section.
- Stop implementation for any marker that cannot be classified with direct current file:line evidence.
- Stop and route the precise prerequisite packet if a marker is not `removable-now` and its structural prerequisite cannot be satisfied inside this wave.
- Stop if a proposed fix depends on baseline updates, host exception tables, smarter Python/JavaScript behavior, or `bootstrap_core.js:293`.
- Stop if Python/JavaScript parity cannot be preserved, unless the packet records a substrate-specific proof and routes it explicitly.
- Stop and do not claim completion if focused tests, host-semantics ratchet, host-authority inventory ratchet, strict L4 contract, indicator collection, or required docs consistency checks fail.

## Acceptance Criteria

- This packet contains explicit Scope, Work Items, Constraints, Stop Conditions, Acceptance Criteria, and Grounding / Authorization sections.
- Same-wave tracker authority before Phase B starts must be proven by a TASKS-only command: `rg -n "n3-stage0-match-substitute-host-semantics-reduction-2026-05-19|FOUNDER_OVERRIDE:n3-stage0-match-substitute-host-semantics-reduction-2026-05-19" TASKS.md` must exit 0 and return a detector-visible `TASKS.md` tracker entry for this exact wave ID or same-wave override.
- Packet-local matches, including the `FOUNDER_OVERRIDE` in this file, are not sufficient tracker authority; a combined packet-plus-`TASKS.md` search may be used only as secondary display after the TASKS-only command passes.
- Phase B classification table covers all selected markers in the scoped Python and JavaScript line windows with direct current file:line evidence.
- Any implemented removal or reduction is parity-preserving across Python and JavaScript, or the packet records and routes a substrate-specific proof before implementation.
- Host-semantics ratchet shows no new host-semantic marker counts; any claimed reduction is reflected in the selected marker evidence and ratchet result.
- Host-authority inventory ratchet reports no unaccepted new total-inventory or authority-subset sites.
- Focused Stage0/parity negative controls pass for the selected marker behavior; broad unrelated tests are not substituted for direct evidence.
- Strict L4 execution contract passes for the final wave class and owned files.
- Indicator collection emits `reports/l4_wave_indicators/n3-stage0-match-substitute-host-semantics-reduction-2026-05-19.json`.
- If no marker is honestly removable/reducible, the accepted outcome is a precise prerequisite packet route, not a false reduction claim.

## Phase B Classification / Route

Same-wave tracker authority was added before runtime edits. The required TASKS-only authority command now exits 0 and returns the same-wave tracker entry:

`rg -n "n3-stage0-match-substitute-host-semantics-reduction-2026-05-19|FOUNDER_OVERRIDE:n3-stage0-match-substitute-host-semantics-reduction-2026-05-19" TASKS.md`

No selected marker is `removable-now` in this bounded wave. The selected markers still describe live Stage0 host recursion or Python host builtins in the current source, and the structural prerequisite is not satisfied inside this packet without adding new host semantics or touching out-of-scope runtime surfaces.

| Marker | Classification | Current file:line evidence | Parity implication |
| --- | --- | --- | --- |
| `mu/host/python/rcx_pi/selfhost/eval_seed.py` `_stage0_match` `@host_recursion` | `structurally-reducible-with-prerequisite` | Marker remains at `eval_seed.py:524-528`; `_stage0_match` still recursively calls itself at `eval_seed.py:595-596`. | JS mirror remains recursive at `bootstrap_core.js:441-445` and `bootstrap_core.js:505-506`; any reduction must change both substrates or route a substrate-specific proof before implementation. |
| `mu/host/python/rcx_pi/selfhost/eval_seed.py` `_stage0_match` `@host_builtin` | `structurally-reducible-with-prerequisite` | Marker remains at `eval_seed.py:529-533`; current body still uses the named host builtins/type dispatch and object APIs at `eval_seed.py:544`, `eval_seed.py:555-567`, `eval_seed.py:571-572`, `eval_seed.py:581-587`, and `eval_seed.py:591`. | Python-only marker removal would be false and parity-skewed because JS still uses equivalent host object/type facilities in the Stage0 match path at `bootstrap_core.js:453-491` and `bootstrap_core.js:500-506`. |
| `mu/host/python/rcx_pi/selfhost/eval_seed.py` `_stage0_substitute` `@host_recursion` | `structurally-reducible-with-prerequisite` | Marker remains at `eval_seed.py:603-609`; `_stage0_substitute` still recursively calls itself for dict and list traversal at `eval_seed.py:623-630`. | JS mirror remains recursive at `bootstrap_core.js:515-518`, `bootstrap_core.js:533-534`, and `bootstrap_core.js:536-538`; any reduction must preserve Python/JS behavior together. |
| `mu/host/js/core/bootstrap_core.js` `stage0Match` `@host_recursion` | `structurally-reducible-with-prerequisite` | Marker remains at `bootstrap_core.js:441-445`; `stage0Match` still recursively calls itself at `bootstrap_core.js:505-506`. | Python mirror remains recursive at `eval_seed.py:524-528` and `eval_seed.py:595-596`; JS-only removal would underreport the live cross-substrate Stage0 recursion boundary. |
| `mu/host/js/core/bootstrap_core.js` `stage0Substitute` `@host_recursion` | `structurally-reducible-with-prerequisite` | Marker remains at `bootstrap_core.js:515-518`; `stage0Substitute` still recursively calls itself at `bootstrap_core.js:533-534` and `bootstrap_core.js:536-538`. | Python mirror remains recursive at `eval_seed.py:603-609` and `eval_seed.py:623-630`; parity-preserving reduction requires a shared structural replacement, not a substrate-local marker edit. |

Precise prerequisite route:

- Successor packet route: `reports/control_plane/n3-stage0-match-substitute-structural-worklist-prerequisite-2026-05-19.md`.
- Routed packet status: materialized as a route-only prerequisite packet. It does not authorize runtime, substrate, seed, ratchet, or test edits until the successor packet first gains detector-visible `TASKS.md` tracker authority for its exact wave ID and packet path.
- Required successor purpose: replace the selected Stage0 recursive host tree walks and Python builtin/type-dispatch marker with a parity-preserving structural worklist or self-hosted match/substitute default-path reduction, expressed in Mu/Stage0 structure rather than Python or JavaScript host semantics.
- Required successor authority before implementation: a detector-visible same-wave `TASKS.md` tracker entry, explicit Python/JS write set, focused Stage0/parity negative controls proving behavior and marker reduction, host-semantics ratchet proof with no baseline update, host-authority inventory ratchet proof, strict L4 structural contract, and indicator collection.
- Current wave outcome: no runtime code edits; no selected marker removal; no host-semantics reduction claim.

## Grounding / Authorization

- Governing packet: `reports/control_plane/n3-stage0-match-substitute-host-semantics-reduction-2026-05-19_2026-05-19.md`.
- Same-wave override for commit automation: `FOUNDER_OVERRIDE:n3-stage0-match-substitute-host-semantics-reduction-2026-05-19`.
- `reports/control_plane/post_redteam_structural_queue_2026-03-20.md:110-113` requires a separate bounded control-plane packet and detector-visible `TASKS.md` tracker entry before new structural reduction beyond listed queue state; this file is the bounded packet side of that requirement.
- `TASKS.md:381` records predecessor wave `n3-host-semantics-ratchet-removal-source-lock-2026-05-19` only. It is authorization evidence for the completed source-lock and selected downstream slice, not sufficient implementation authority for this successor before a same-wave tracker entry exists.
- Predecessor evidence: `reports/control_plane/n3-host-semantics-ratchet-removal-source-lock-2026-05-19_2026-05-19.md` is `IMPLEMENTED / LOCAL EVIDENCE` for the source-lock slice and explicitly excludes `mu/host/js/core/bootstrap_core.js:293`.
- This packet may authorize only Phase A packetization and same-wave tracker synchronization until the `TASKS.md` same-wave tracker check passes.

End all generated founder-facing prompts/reports with: Questions? Concerns? Thoughts? -- Think hard

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `n3-stage0-match-substitute-host-semantics-reduction-2026-05-19`
- Active packet: `reports/control_plane/n3-stage0-match-substitute-host-semantics-reduction-2026-05-19_2026-05-19.md`
- Indicator artifact: `reports/l4_wave_indicators/n3-stage0-match-substitute-host-semantics-reduction-2026-05-19.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `reports/control_plane/n3-stage0-match-substitute-host-semantics-reduction-2026-05-19_2026-05-19.md`
  - `reports/l4_wave_indicators/n3-stage0-match-substitute-host-semantics-reduction-2026-05-19.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `n3-stage0-match-substitute-host-semantics-reduction-2026-05-19`
- Active packet: `reports/control_plane/n3-stage0-match-substitute-host-semantics-reduction-2026-05-19_2026-05-19.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `c9fdbd4238f70a513ebf2be4311464a0a2d13f6a659cb3ac323f2107fba4508c`
- Indicator artifact: `reports/l4_wave_indicators/n3-stage0-match-substitute-host-semantics-reduction-2026-05-19.json`
- Evidence command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id n3-stage0-match-substitute-host-semantics-reduction-2026-05-19 --output reports/l4_wave_indicators/n3-stage0-match-substitute-host-semantics-reduction-2026-05-19.json`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/n3-stage0-match-substitute-host-semantics-reduction-2026-05-19_2026-05-19.md. (2) Commit handoff carries 3 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/n3-stage0-match-substitute-host-semantics-reduction-2026-05-19.json`
- Current staged files:
  - `TASKS.md`
  - `reports/control_plane/n3-stage0-match-substitute-host-semantics-reduction-2026-05-19_2026-05-19.md`
  - `reports/l4_wave_indicators/n3-stage0-match-substitute-host-semantics-reduction-2026-05-19.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
