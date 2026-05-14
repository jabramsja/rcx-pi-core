# Broad-Host-Surface-N3-Source-Boundary-Slice-2026-05-14

Date: 2026-05-14
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: broad-host-surface-n3-source-boundary-slice-2026-05-14
Class: L4_ENABLER
target_gate_id: G8
workload_target: host_debt_reduction
Phase-A-Lock: LOCKED
FOUNDER_OVERRIDE:broad-host-surface-n3-source-boundary-slice-2026-05-14
Authorization: standing packet-local authorization for this packet-only control-surface rewrite.
Purpose: Route the still-active N3 broad host-surface deferred residue into exactly one source-grounded `/mu` structural host-surface reduction candidate without pretending that one bounded slice closes the retained N3 advisory.

## Scope

Read-only grounding scope for this Phase A rewrite:

- `reports/control_plane/broad-host-surface-n3-source-boundary-slice-2026-05-14_2026-05-14.md`
- `reports/control_plane/broad_host_surface_next_structural_slice_2026-05-13.md`
- `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md`
- `reports/deferred/non_blocking/README.md`
- `reports/deferred/README.md`
- `STATUS.md`
- `TASKS.md`

Candidate inspection scope used to ground the selected slice:

- `mu/host/js/core/stage0_vm.js`
- `mu/host/js/core/seed_loader.js`
- `mu/host/js/cli/main.js`
- `mu/host/python/rcx_pi/selfhost/stage0_vm.py`
- `mu/tests/l4_gates/test_stage0_vm.py`
- `mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py`
- current host-semantics and host-authority ratchet outputs from startup

Writable scope for this packet rewrite:

- `reports/control_plane/broad-host-surface-n3-source-boundary-slice-2026-05-14_2026-05-14.md` only

This rewrite does not authorize runtime implementation edits. Any follow-on
implementation package must keep the selected write set below unless source
truth proves the stop conditions are hit.

## Work items

1. Grounded open N3 status from active deferred docs and TASKS evidence:
   `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md:161`
   through `:175` keeps N3 active, requires a separate bounded successor
   packet before implementation, and forbids moving Mu semantic authority into
   Python or JavaScript host code. `reports/deferred/non_blocking/README.md:341`
   through `:349` and `reports/deferred/README.md:22` through `:56` keep the
   active non-blocking lane to the README plus the retained repo-truth packet,
   with N3 broad host-surface boundary as the live advisory.
2. Treated `TASKS.md:320`, `TASKS.md:570`, and `TASKS.md:574` as active
   inventory evidence for retained N3 residue, while treating `TASKS.md:328`,
   `TASKS.md:329`, and `TASKS.md:331` as predecessor-wave evidence, not pending
   work.
3. Read the predecessor packet. `reports/control_plane/broad_host_surface_next_structural_slice_2026-05-13.md:52`
   through `:61` records that PR #944 and PR #945 closed prior JS
   acceptance-boundary slices, including the exported JS Stage0
   `muCopy(..., rejectNonMu=true)` host-trap fail-closed path, but did not close
   N3. `:175` through `:204` records the same-wave dispatcher/package repair.
   Those items are not reopened here.
4. Inspected current source and focused tests around the still-exported JS
   Stage0 copy boundary. The selected candidate below is tied to concrete
   source/test evidence and is not selected by deferred-text word matching.
5. Selected exactly one bounded candidate: **JS Stage0 exported `muCopy`
   lax-mode confinement**.
6. Left N3 active after this handoff. Even if the selected slice later lands,
   it closes only one public JS host-copy boundary and does not prove broad
   host-surface closure.

## Selected Candidate

Candidate: **JS Stage0 exported `muCopy` lax-mode confinement**.

Current code truth:

- `mu/host/js/core/stage0_vm.js:207` defines `muCopy(value, rejectNonMu = false, context = 'Deep copy')`, so the exported copy helper defaults to lax mode.
- `mu/host/js/core/stage0_vm.js:209` through `:213` canonicalizes `undefined` to `null` when lax mode is used, and `:288` through `:292` returns `null` for non-Mu host values when `rejectNonMu` is false.
- `mu/host/js/core/stage0_vm.js:1043` through `:1053` exports `muCopy` from the Stage0 VM module, so this lax host-copy behavior remains reachable through the public JS module surface.
- `mu/tests/l4_gates/test_stage0_vm.py:1538` through `:1606` proves the current focused test locks the strict trap behavior and also treats `muCopy(value, false, ...)` as successfully completed for hostile proxy/revoked-proxy cases. That is the current unclosed slice; it is not the predecessor's `rejectNonMu=true` trap repair.
- Legitimate checked parse-tree ingress already calls the helper in strict mode:
  `mu/host/js/core/seed_loader.js:205`, `mu/host/js/cli/main.js:245` through
  `:249`, and `mu/host/js/cli/main.js:355` through `:359` use
  `muCopy(..., true, ...)` for checksum/API fixture parse-tree ingress.
- The paired Python surface is narrower: `mu/host/python/rcx_pi/selfhost/stage0_vm.py:202`
  through `:224` keeps the lax copy helper under private `_mu_copy`, and
  `mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py:154` through `:185`
  already bans module-level Python `stage0_vm` namespace access outside the
  allowlist to prevent `_func()` access. This makes the selected Phase B
  candidate JS-only unless implementation evidence finds a Python parity gap.

Proposed Phase B locked write set:

- `mu/host/js/core/stage0_vm.js`
- `mu/tests/l4_gates/test_stage0_vm.py`
- `mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py`

Expected structural artifact refs:

- `mu/host/js/core/stage0_vm.js`: split or wrap the exported copy boundary so
  externally reachable `muCopy` cannot enter lax `rejectNonMu=false` mode, while
  internal template materialization can still use private lax copying where the
  VM already owns the bundle/capture context.
- `mu/tests/l4_gates/test_stage0_vm.py`: replace the current lax-completion
  expectation with a fail-closed exported-boundary expectation and keep the
  existing strict `rejectNonMu=true` host-trap proof.
- `mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py`: source-lock the
  public JS Stage0 VM copy export so future edits cannot re-expose a lax public
  host-copy path or a new public trust/copy mutator.

Focused Phase B validation commands:

```bash
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_stage0_vm.py::TestCapturePathProvenance mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py::TestJsSourceLock --tb=short -p no:cacheprovider
node mu/host/js/eval_step.js
python3 mu/tools/checks/check_host_semantics_ratchet.py --json
python3 tools/checks/check_host_authority_inventory_ratchet.py
./tools/checks/check_docs_consistency.sh
```

Parity and ratchet obligations:

- Preserve Python/JS runtime parity for Stage0 VM stepping. The selected slice
  should change only exported JS host-boundary accessibility, not Stage0 opcode
  semantics, seed semantics, kernel dispatch, or Python behavior.
- Host-semantics ratchet must not increase. Startup evidence before this packet
  reported the host-semantics ratchet passed with no increases.
- Host-authority inventory must not add total-inventory or authority-subset
  sites. Startup evidence before this packet reported `311 total (181 Python +
  130 JS)` current sites versus `312 total (181 Python + 131 JS)` baseline, and
  `217 authority` current and baseline sites with no new total or authority
  sites.
- Do not update ratchet baselines as evidence for this slice. A real reduction
  must be proven by source/test behavior and no ratchet increase.

Proof limits:

- This candidate shrinks one JS public host-copy boundary. It does not eliminate
  the Stage0 VM, the JS substrate, the Python substrate, bootstrap primitives,
  seed loading, scheduler behavior, registry behavior, production `/mu` scope,
  or N3 as a retained broad host-surface advisory.
- If Phase B discovers the public lax export is already closed by current code
  before edits begin, Phase B must stop and record no-slice closure evidence
  instead of inventing adjacent work.

## Constraints

- This packet authorizes Phase A candidate selection and packet convergence only.
- Do not edit Claude-related files, Claude home files, `.claude/`, or
  Claude-specific run surfaces.
- Do not create semantic host debt, host-only oracles, public trust mutators,
  public constructor laundering paths, or new Python/JavaScript authority sites.
- Do not move Mu semantic decisions into Python or JavaScript host code. The
  selected candidate must shrink a public host-copy boundary, not make the host
  smarter.
- Do not use word matching alone to select or implement the candidate.
- Do not carry already-landed predecessor work as pending. The strict
  `muCopy(..., rejectNonMu=true)` host-trap repair and predecessor dispatcher
  package repair remain predecessor evidence only.
- Do not widen to unrelated deferred advisories, runtime rewrites, seed
  semantics, scheduler work, registry redesign, production `/mu` scope,
  host-oracle work, or docs cleanup outside the selected boundary.
- Preserve Python/JavaScript parity where behavior is semantically shared.
- Future Phase B must not require files outside the proposed locked write set
  unless it stops and emits a new bounded packet.

## Stop conditions

- Stop if the only viable implementation would add host-only semantics, new host
  authority, a host oracle, or a public trust/constructor laundering path.
- Stop if the selected candidate requires edits outside the proposed write set
  or requires Claude-related files.
- Stop if parity cannot be preserved or the needed proof would be asymmetric
  across Python and JavaScript for shared behavior.
- Stop if current code truth proves the apparent public lax `muCopy` boundary is
  already closed.
- Stop if Phase B cannot source-lock the exported JS copy boundary without
  breaking legitimate strict parse-tree ingress at `seed_loader.js` and
  `cli/main.js`.
- Stop if the implementation would change Stage0 opcode semantics, seed
  semantics, scheduler behavior, registry behavior, production `/mu` boundaries,
  or any unrelated retained deferred advisory.

## Acceptance criteria

- The packet contains detector-visible `Scope`, `Work items`, `Constraints`,
  `Stop conditions`, `Acceptance criteria`, and `Grounding / Authorization`
  sections.
- The packet contains
  `FOUNDER_OVERRIDE:broad-host-surface-n3-source-boundary-slice-2026-05-14` so
  same-wave control-surface authorization can be derived without editing
  `TASKS.md` in this packet-only rewrite.
- Phase A selects exactly one current source-grounded `/mu` host-surface
  reduction candidate: JS Stage0 exported `muCopy` lax-mode confinement.
- The selected candidate includes concrete current file/line evidence, a
  proposed locked write set, focused validation commands, parity obligations,
  and ratchet expectations.
- The selected candidate does not re-open predecessor broad-host-surface work
  already represented by `TASKS.md:328`, `TASKS.md:329`, or `TASKS.md:331`
  unless future current-code truth specifically disproves that predecessor
  state.
- The selected candidate does not authorize Claude-related edits, host-oracle
  work, semantic host debt, public constructor laundering, or files outside the
  proposed locked write set.
- Packet-shape verification should pass with:
  `rg -n "^(## )?(Scope|Work items|Work Items|Constraints|Stop conditions|Stop Conditions|Acceptance criteria|Acceptance Criteria|Grounding|Authorization)|FOUNDER_OVERRIDE|Authorization: standing" reports/control_plane/broad-host-surface-n3-source-boundary-slice-2026-05-14_2026-05-14.md`

## Grounding / Authorization

- Governing packet:
  `reports/control_plane/broad-host-surface-n3-source-boundary-slice-2026-05-14_2026-05-14.md`
- Task: `[NEXT-CODEX-POST-REDTEAM]`
- Wave ID: `broad-host-surface-n3-source-boundary-slice-2026-05-14`
- Packet-local authorization:
  `FOUNDER_OVERRIDE:broad-host-surface-n3-source-boundary-slice-2026-05-14`
- TASKS grounding: `TASKS.md:320` says the transparent Proxy deferred advisory
  was closed and the active deferred non-blocking residue became N3 broad
  host-surface boundary only.
- TASKS grounding: `TASKS.md:328` and `TASKS.md:329` record completed
  broad-host-surface structural predecessor handoffs with explicit evidence,
  ratchet expectations, and same-wave overrides.
- TASKS grounding: `TASKS.md:331` records the predecessor
  `reports/control_plane/broad_host_surface_next_structural_slice_2026-05-13.md`
  Phase B handoff and pending pre-commit supervisor package refresh.
- TASKS grounding: `TASKS.md:570` and `TASKS.md:574` keep N3 broad
  host-surface boundary active in deferred inventory while excluding unrelated
  runtime, Stage0, seed, scheduler, registry, parity, production `/mu`,
  host-oracle, and Claude-related changes.
- Reviewer evidence for this rewrite is authoritative:
  `rg -n "broad-host-surface-n3-source-boundary-slice-2026-05-14" TASKS.md`
  had no matches for this new wave ID, so this packet supplies the wave-bound
  packet authorization line instead of claiming TASKS already has same-wave
  tracker authority.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `broad-host-surface-n3-source-boundary-slice-2026-05-14`
- Active packet: `reports/control_plane/broad-host-surface-n3-source-boundary-slice-2026-05-14_2026-05-14.md`
- Indicator artifact: `reports/l4_wave_indicators/broad-host-surface-n3-source-boundary-slice-2026-05-14.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `reports/control_plane/broad-host-surface-n3-source-boundary-slice-2026-05-14_2026-05-14.md`
  - `reports/l4_wave_indicators/broad-host-surface-n3-source-boundary-slice-2026-05-14.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `broad-host-surface-n3-source-boundary-slice-2026-05-14`
- Active packet: `reports/control_plane/broad-host-surface-n3-source-boundary-slice-2026-05-14_2026-05-14.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `97e4f19b7b593e827ad3ba99bfdab951cf35240f1a8933bf7442d2a74fc526c2`
- Indicator artifact: `reports/l4_wave_indicators/broad-host-surface-n3-source-boundary-slice-2026-05-14.json`
- Evidence command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id broad-host-surface-n3-source-boundary-slice-2026-05-14 --output reports/l4_wave_indicators/broad-host-surface-n3-source-boundary-slice-2026-05-14.json`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/broad-host-surface-n3-source-boundary-slice-2026-05-14_2026-05-14.md. (2) Commit handoff carries 3 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/broad-host-surface-n3-source-boundary-slice-2026-05-14.json`
- Current staged files:
  - `TASKS.md`
  - `reports/control_plane/broad-host-surface-n3-source-boundary-slice-2026-05-14_2026-05-14.md`
  - `reports/l4_wave_indicators/broad-host-surface-n3-source-boundary-slice-2026-05-14.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
