# N3-Stage0-Match-Substitute-Structural-Worklist-Implementation-2026-05-19

Date: 2026-05-19
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-stage0-match-substitute-structural-worklist-implementation-2026-05-19
Class: L4_STRUCTURAL
Target gate: G8
Packet path: reports/control_plane/n3-stage0-match-substitute-structural-worklist-implementation-2026-05-19_2026-05-19.md
Phase-A-Lock: LOCKED
Purpose: Route the Stage0 match/substitute structural worklist implementation wave without adding host semantics, without creating a second control packet path, and without treating the prerequisite tracker note as implementation-wave authority.

## Scope

This Phase A packet rewrite touched only:

- `reports/control_plane/n3-stage0-match-substitute-structural-worklist-implementation-2026-05-19_2026-05-19.md`

Future Phase B implementation, after same-wave `TASKS.md` authority exists, may touch only this subset:

- `TASKS.md` for same-wave detector-visible tracker authority and no runtime behavior.
- `reports/control_plane/n3-stage0-match-substitute-structural-worklist-implementation-2026-05-19_2026-05-19.md` for this reviewed packet path only.
- `reports/l4_wave_indicators/n3-stage0-match-substitute-structural-worklist-implementation-2026-05-19.json` for indicator collection.
- `mu/host/python/rcx_pi/selfhost/eval_seed.py` for Stage0 match/substitute structural worklist/default-path reduction.
- `mu/host/js/core/bootstrap_core.js` for the JavaScript parity mirror of the same reduction.
- `mu/tests/l4_gates/test_stage0_production_pilot_gate.py`
- `mu/tests/l4_gates/test_w3_crash_guards_gate.py`
- `mu/tests/parity/test_js_vm_bridge_parity.py`
- `mu/tests/structural/test_execution_layer_truth_contract.py`

The reviewed packet path is the suffixed path above. Do not create a second unsuffixed control packet for this Phase A plan.

## Work Items

1. Before any runtime edit, add detector-visible same-wave `TASKS.md` authority for `n3-stage0-match-substitute-structural-worklist-implementation-2026-05-19`. The current fixed-string search for that implementation wave in `TASKS.md` exits 1 with no output; `TASKS.md:383` authorizes only the prerequisite wave.
2. Re-open current Python and JavaScript Stage0 match/substitute code before proposing edits. Classify each target marker and traversal site with fresh file:line evidence. If current code truth proves a listed item is already implemented, remove that item from pending work and acceptance criteria instead of relisting it as unresolved.
3. Implement only parity-preserving structural reduction for selected Stage0 match/substitute recursion. Prefer explicit worklist/default-path structure in both Python and JavaScript; do not add host exception tables, substrate-only semantic inference, or smarter host behavior.
4. Claim only reductions proven by the implementation. A recursion-only rewrite may claim selected `@host_recursion` reduction. Do not claim the Python `@host_builtin` marker removed unless the wave also proves self-hosted Mu/Stage0 default-path structural dispatch or equivalent structural dispatch with no Python-only or JavaScript-only semantic inference.
5. Extend or adjust only the focused Stage0/parity control bundle named by the prerequisite packet: direct Stage0 canonical/negative controls, Python/JS compiled match/substitute parity, and the D005 Stage0 contract check represented by the required pytest bundle.
6. Collect wave indicators and validation proof without baseline updates. Any marker decrease must be proven as a source/runtime change, not a baseline edit.

## Constraints

- Do not treat the current prerequisite tracker note as implementation-wave authority.
- Do not perform runtime edits while the implementation wave lacks a detector-visible `TASKS.md` tracker entry.
- Do not create or lock a second control packet path for this Phase A plan.
- Do not inspect or edit unrelated dirty files, git diffs, executor changes, test changes, or downstream implementation files as part of this Phase A rewrite.
- Do not touch `mu/host/js/core/bootstrap_core.js:293` projection-loop dispatch.
- Do not add host-only semantics, Python-only behavior, JavaScript-only behavior, host exception tables, new authority sites, or ratchet baseline changes.
- Do not widen into seeds, registry, scheduler, loader, binary/TLV, checksum/integrity, production default flips, dispatcher/commit/push/PR surfaces, Claude files, or unrelated tooling.
- Do not relist work as unresolved when current code truth proves it has already landed.

## Stop Conditions

Stop before runtime edits if any of these occur:

- `rg -n -F "n3-stage0-match-substitute-structural-worklist-implementation-2026-05-19" TASKS.md` still has no same-wave implementation match.
- The wave cannot add same-wave `TASKS.md` tracker authority within the allowed write set.
- Re-opened code evidence shows the requested reduction is already implemented; update the packet/tracker truth instead of editing runtime code.
- The reduction would require host exception tables, new host semantics, ratchet baseline updates, or Python/JavaScript semantic divergence.
- The implementation requires files outside the scoped subset.
- Focused Stage0/parity controls, `node mu/host/js/eval_step.js`, host-semantics ratchet, host-authority inventory ratchet, strict L4 structural enforcement, indicator collection, or docs consistency fail.
- Any generated prompt/report cannot end with the founder footer.

## Acceptance Criteria

- This reviewed packet remains the governing Phase A packet at `reports/control_plane/n3-stage0-match-substitute-structural-worklist-implementation-2026-05-19_2026-05-19.md`; no unsuffixed duplicate packet is created.
- `TASKS.md` contains detector-visible same-wave implementation authority for `n3-stage0-match-substitute-structural-worklist-implementation-2026-05-19` before runtime edits begin.
- Fresh file:line evidence classifies the exact current Python and JavaScript Stage0 match/substitute target markers and traversal sites before edits.
- Python and JavaScript changes are parity mirrors and reduce selected host recursion through structural worklist/default-path execution rather than added host semantics.
- Any `@host_recursion` decrease is proven by source/runtime change and indicator output, not by ratchet baseline updates.
- No Python `@host_builtin` removal is claimed unless self-hosted/default-path structural dispatch is implemented and proven without Python-only or JavaScript-only semantic inference.
- Required focused controls pass:

```bash
PYTHONHASHSEED=0 python3 -m pytest -q \
  mu/tests/l4_gates/test_stage0_production_pilot_gate.py::TestStage0CanonicalVectors \
  mu/tests/l4_gates/test_stage0_production_pilot_gate.py::TestParityWithMatchInner \
  mu/tests/l4_gates/test_w3_crash_guards_gate.py::TestF11EmptyVarNameNoMatch \
  mu/tests/l4_gates/test_w3_crash_guards_gate.py::TestF25JsStage0MatchEmptyVar \
  mu/tests/parity/test_js_vm_bridge_parity.py::TestMatchVmBridgeParity \
  mu/tests/parity/test_js_vm_bridge_parity.py::TestSubstVmBridgeParity \
  mu/tests/structural/test_execution_layer_truth_contract.py::TestD005Stage0Contract \
  --tb=short
node mu/host/js/eval_step.js
```

- Required ratchet, indicator, strict contract, and docs checks pass without baseline updates:

```bash
python3 mu/tools/checks/check_host_semantics_ratchet.py --json
python3 tools/checks/check_host_authority_inventory_ratchet.py
python3 tools/metrics/collect_l4_wave_indicators.py --wave-id n3-stage0-match-substitute-structural-worklist-implementation-2026-05-19 --output reports/l4_wave_indicators/n3-stage0-match-substitute-structural-worklist-implementation-2026-05-19.json
python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id n3-stage0-match-substitute-structural-worklist-implementation-2026-05-19 --wave-class L4_STRUCTURAL
./tools/checks/check_docs_consistency.sh
```

## Phase B Implementation Evidence

- Same-wave `TASKS.md` authority was added before runtime edits:
  `TASKS.md:384` now contains `n3-stage0-match-substitute-structural-worklist-implementation-2026-05-19`.
- Bridge repair re-opened Python evidence:
  `mu/host/python/rcx_pi/selfhost/eval_seed.py:524-529` carries the non-targeted
  `_stage0_match` `@host_builtin` marker with no `_stage0_match`
  `@host_recursion` marker; `:532-595` is explicit worklist traversal.
  `mu/host/python/rcx_pi/selfhost/eval_seed.py:601-605` retains
  `_stage0_substitute` `@host_recursion` as a P7 debt-dashboard marker, while
  `:607-646` is explicit work/value-stack traversal with no self-recursive
  `_stage0_substitute(...)` call and no `.append()` worklist mutation.
- Bridge repair re-opened JavaScript evidence:
  `mu/host/js/core/bootstrap_core.js:443-446` and `:528-530` retain the legacy
  JS `@host_recursion` debt-dashboard comments, while `:448-523` and `:531-582`
  are explicit worklist/value-stack traversal with no `stage0Match(...)` or
  `stage0Substitute(...)` self-recursive traversal calls beyond function
  declarations.
- Implemented reduction:
  Python `_stage0_match` now uses an explicit worklist at
  `mu/host/python/rcx_pi/selfhost/eval_seed.py:532-595`;
  Python `_stage0_substitute` now uses an explicit work/value stack at
  `mu/host/python/rcx_pi/selfhost/eval_seed.py:607-646`;
  JavaScript `stage0Match` now uses an explicit worklist at
  `mu/host/js/core/bootstrap_core.js:448-517`;
  and JavaScript `stage0Substitute` now uses an explicit work/value stack at
  `mu/host/js/core/bootstrap_core.js:531-582`.
- Claim boundary:
  this wave claims selected Stage0 `@host_recursion` reduction only for the
  Python `_stage0_match` marker. Python `_stage0_substitute` and JavaScript
  Stage0 self-calls are structurally removed, but their legacy
  debt-dashboard `@host_recursion` markers/comments remain because the scoped
  P7/JS checker contracts still require them and checker updates are outside
  this wave write set.
  Python `_stage0_match` still carries `@host_builtin` at
  `mu/host/python/rcx_pi/selfhost/eval_seed.py:524`; no Python builtin/default-dispatch
  removal is claimed.

## Grounding / Authorization

- `TASKS.md:3-4` makes `TASKS.md` the single source of truth and forbids implementing unlisted tasks.
- `TASKS.md:559-563` keeps `[NEXT-CODEX-POST-REDTEAM]` unparked, founder-authorized, and open for remaining bounded structural reduction packets.
- `TASKS.md:567` requires every wave to have a control-plane packet plus a `TASKS.md` tracker entry.
- `TASKS.md:383` authorizes only `n3-stage0-match-substitute-structural-worklist-prerequisite-2026-05-19`; it is not same-wave implementation authority.
- Before Phase B tracker sync, the fixed-string search for `n3-stage0-match-substitute-structural-worklist-implementation-2026-05-19` in `TASKS.md` exited 1 with no output; `TASKS.md:384` now supplies the required same-wave implementation authority.
- Governing prerequisite packet `reports/control_plane/n3-stage0-match-substitute-structural-worklist-prerequisite-2026-05-19.md:116-124` allows only later `L4_STRUCTURAL` packetization of a parity-preserving structural worklist/default-path reduction and forbids claiming Python `@host_builtin` removal from a recursion-only rewrite.
- Governing prerequisite packet `reports/control_plane/n3-stage0-match-substitute-structural-worklist-prerequisite-2026-05-19.md:126-137` bounds the successor write set. This reviewed Phase A packet uses the current suffixed packet path as the governing packet path and does not create another control packet.
- Governing prerequisite packet `reports/control_plane/n3-stage0-match-substitute-structural-worklist-prerequisite-2026-05-19.md:139-163` names the focused pytest bundle, `node mu/host/js/eval_step.js`, host-semantics ratchet, host-authority inventory ratchet, indicator collection, strict L4 structural enforcement, and docs consistency as required successor proof.
- Reviewer-confirmed prerequisite evidence: `reports/control_plane/n3-stage0-match-substitute-structural-worklist-prerequisite-2026-05-19.md:140` names only direct Stage0 canonical/negative controls and Python/JS compiled match/substitute parity, and `reports/control_plane/n3-stage0-match-substitute-structural-worklist-prerequisite-2026-05-19.md:150` names `TestD005Stage0Contract`; this packet does not treat any finer-grained category list as prerequisite-grounded pending work.
- Same-wave packet authorization for this control packet rewrite: FOUNDER_OVERRIDE:n3-stage0-match-substitute-structural-worklist-implementation-2026-05-19. This packet override does not replace the required `TASKS.md` same-wave tracker entry before runtime edits.

Questions? Concerns? Thoughts? -- Think hard
