# JS Bridge VM Ordering Evidence

Date: 2026-05-10
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: js-bridge-vm-ordering-evidence-2026-05-09
Phase-A-Lock: LOCKED
Class: L4_ENABLER
Category: /mu structural evidence
Source authorization: TASKS.md:510; routed-by-repo-truth-mu-structural-advisory-triage-2026-05-09
Routing source: reports/control_plane/repo_truth_mu_structural_advisory_triage_2026-05-09.md
Same-wave override: FOUNDER_OVERRIDE:js-bridge-vm-ordering-evidence-2026-05-09

## Phase B Evidence Result

Result: PROOF GAP REMAINS.

Current code truth:

- `mu/host/js/engine/kernel.js:44` through `mu/host/js/engine/kernel.js:63`
  source-locks `_stepKernelWithVM()` to try the Stage0 bundles in this order:
  `kernelBundle`, optional `bridgeBundle`, `matchBundle`, then `substBundle`.
- `mu/host/js/tests/self_tests.js:446` through
  `mu/host/js/tests/self_tests.js:459` prove bridge projection ordering
  validation and negative validation cases.
- `mu/host/js/tests/self_tests.js:461` through
  `mu/host/js/tests/self_tests.js:514` prove bridge-mode smoke through
  `stepKernel()`, `runStructural()`, and a stall case with `vmConfigBridge`.
- `mu/tests/parity/test_js_vm_bridge_parity.py:72` through
  `mu/tests/parity/test_js_vm_bridge_parity.py:264` prove Python/JS Stage0
  parity for the individual `match.v2`, `subst.v2`, `kernel.v1`, and
  `bootstrap_structural.v1` compiled bundles.

Reproduced local evidence:

- `set -o pipefail; node mu/host/js/eval_step.js | rg
  "Bridge ordering|Valid bridge|Missing bridge|Bridge-after|Non-dict|PASS bridge|Bridge-mode"`
  exited `0` and reported successful bridge ordering validation plus
  `PASS bridge-mode VM shadow: true`.
- `PYTHONHASHSEED=0 python3 -m pytest -q
  mu/tests/parity/test_js_vm_bridge_parity.py` exited `0` with
  `12 passed in 0.92s`.
- `nl -ba mu/host/js/tests/self_tests.js | sed -n '461,514p' &&
  nl -ba mu/host/js/engine/kernel.js | sed -n '23,27p' &&
  rg -n
  "js-bridge-vm-ordering-evidence-2026-05-09|js_bridge_vm_ordering_evidence_2026-05-09.md"
  TASKS.md reports/control_plane/js_bridge_vm_ordering_evidence_2026-05-09.md
  reports/deferred/non_blocking/*.md` exited `0` and reproduced the current
  source/packet/tracker evidence.

Decision:

- Current parity tests do not close the exact advisory. They prove individual
  Stage0 bundle parity and JS bridge-mode smoke, but not an end-to-end JS
  behavioral proof that the live Stage0 VM kernel path depends on
  `kernel.v1 -> bridge -> match.v2 -> subst.v2` ordering.
- This is not a coverage-system request. `mu/host/js/engine/kernel.js:23`
  through `mu/host/js/engine/kernel.js:27` must continue to state that JS has
  no coverage system.
- No runtime defect was reproduced. No JS runtime semantics, seed
  registration, scheduler, Stage0 VM, or production behavior change is
  authorized by this packet.

Follow-up routing:

- A later evidence-only packet should name `mu/tests/parity/test_js_vm_bridge_parity.py`
  as the exact pytest evidence file for the missing end-to-end JS bridge-ordering
  proof.
- The proof should execute the existing JS Mu projections and Stage0 VM bundles
  through the existing JS runtime entrypoint, using the already-loaded
  `kernel_v1.compiled.v1.json`, `bootstrap_structural_v1.compiled.v1.json`,
  `match_v2.compiled.v1.json`, and `subst_v2.compiled.v1.json` bundles with
  bridge mode enabled.
- The proof must not import host ordering semantics or add JavaScript ordering
  shortcuts. It should demonstrate that the live JS bridge-mode VM path needs the
  existing bridge bundle before `match.v2` and `subst.v2`, rather than merely
  asserting projection array order or individual bundle parity.

## Scope

Phase A scope is limited to these files:

- `mu/host/js/engine/kernel.js`
- `mu/host/js/tests/self_tests.js`
- `mu/tests/parity/test_js_vm_bridge_parity.py`
- `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md`
- `reports/control_plane/repo_truth_mu_structural_advisory_triage_2026-05-09.md`
- `reports/control_plane/js_bridge_vm_ordering_evidence_2026-05-09.md`
- `TASKS.md` line 510 for `[NEXT-CODEX-POST-REDTEAM]` authorization.

No unnamed focused JS parity test file or directory is in Phase A scope. If
Phase A proves a still-live gap, a later implementation packet must name the
exact evidence file(s) or directory before work begins.

## Work Items

1. Reproduce current JS bridge-mode smoke and ordering evidence.
2. Decide whether the missing proof is an end-to-end JS test for
   `kernel.v1 -> bridge -> match.v2 -> subst.v2` ordering under the Stage0 VM,
   or whether current parity tests already close the advisory.
3. If a proof gap remains, route a later implementation packet limited to
   explicitly named JS/pytest evidence files or directories. The later packet
   must exercise existing Mu projections and Stage0 VM bundles rather than
   adding JavaScript semantic shortcuts.

## Constraints

- No JS runtime semantics, seed registration, scheduler, Stage0 VM, or
  production behavior changes in Phase A.
- No new host-only semantics may be introduced for ordering proof.
- Preserve the fact that `mu/host/js/engine/kernel.js` has no coverage system.
- Do not edit Claude-related files.

## Stop Conditions

- Stop if current JS parity tests already prove the exact bridge ordering claim.
- Stop if the proof would require runtime behavior changes instead of focused
  evidence.
- Stop if Phase A discovers the advisory is actually a coverage-system request;
  route that back to the coverage packet instead of merging scopes.

## Acceptance Criteria

- Phase A identifies the exact remaining JS bridge evidence gap or closes it
  with current command/file evidence.
- Any later implementation packet is evidence-only unless Phase A separately
  proves a runtime defect.
- The packet states how the proof executes existing Mu projections rather than
  importing host ordering semantics.

## Grounding / Authorization

- TASKS.md authorization:
  `TASKS.md:510` binds `[NEXT-CODEX-POST-REDTEAM]` to
  `js-bridge-vm-ordering-evidence-2026-05-09`, this packet path,
  Phase A-only JS bridge ordering evidence work, and
  `FOUNDER_OVERRIDE:js-bridge-vm-ordering-evidence-2026-05-09`.
- Source advisory:
  `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md` N2.
- Routing triage:
  `reports/control_plane/repo_truth_mu_structural_advisory_triage_2026-05-09.md`.
- Authorization:
  TASKS.md tracker sync note plus
  `FOUNDER_OVERRIDE:js-bridge-vm-ordering-evidence-2026-05-09`.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `js-bridge-vm-ordering-evidence-2026-05-09`
- Active packet: `reports/control_plane/js_bridge_vm_ordering_evidence_2026-05-09.md`
- Indicator artifact: `reports/l4_wave_indicators/js-bridge-vm-ordering-evidence-2026-05-09.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `reports/control_plane/js_bridge_vm_ordering_evidence_2026-05-09.md`
  - `reports/l4_wave_indicators/js-bridge-vm-ordering-evidence-2026-05-09.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `js-bridge-vm-ordering-evidence-2026-05-09`
- Active packet: `reports/control_plane/js_bridge_vm_ordering_evidence_2026-05-09.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `898eced134e85f91d1d57352ee5f42d64107145ef2d3bbe3c29b95df041b6037`
- Indicator artifact: `reports/l4_wave_indicators/js-bridge-vm-ordering-evidence-2026-05-09.json`
- Evidence command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id js-bridge-vm-ordering-evidence-2026-05-09 --output reports/l4_wave_indicators/js-bridge-vm-ordering-evidence-2026-05-09.json`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/js_bridge_vm_ordering_evidence_2026-05-09.md. (2) Commit handoff carries 3 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/js-bridge-vm-ordering-evidence-2026-05-09.json`
- Current staged files:
  - `TASKS.md`
  - `reports/control_plane/js_bridge_vm_ordering_evidence_2026-05-09.md`
  - `reports/l4_wave_indicators/js-bridge-vm-ordering-evidence-2026-05-09.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
