# N3-Kernel-Driver-Js-Fuel-Threading-Parity-Proof-2026-05-20 2026-05-20

Date: 2026-05-20
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-kernel-driver-js-fuel-threading-parity-proof-2026-05-20
Phase-A-Lock: LOCKED
Class: L4_ENABLER
Purpose: Use repo evidence first and program in Mu terms, not host semantic shortcuts.

## Scope

This Phase A rewrite writes only this packet:

- `reports/control_plane/n3-kernel-driver-js-fuel-threading-parity-proof-2026-05-20_2026-05-20.md`

Bounded Phase B candidate write surface:

- `mu/tests/parity/test_exhaustion_parity.py`

Bridge Round 1 policy amendment write surfaces:

- `TASKS.md` tracker note classification/evidence sync for this same wave only
- `reports/l4_wave_indicators/n3-kernel-driver-js-fuel-threading-parity-proof-2026-05-20.json`

Bounded Phase B reference and validation surfaces:

- `reports/control_plane/n3-kernel-driver-js-fuel-threading-parity-prereq-2026-05-20_2026-05-20.md:57-120`
- `tests/research/test_d006_h1_fuel_threading.py:40-127`
- `tests/research/test_d006_h1_fuel_threading.py:181-411`
- `tests/research/test_d007_h3_negative_control.py:137-363`
- `mu/tests/parity/test_js_parity_automated.py:37-94`
- `mu/tests/parity/test_exhaustion_parity.py:211-330`
- `mu/host/python/rcx_pi/selfhost/step_mu.py:1163-1172`
- `mu/host/python/rcx_pi/selfhost/step_mu.py:1317-1319`
- `mu/host/js/engine/kernel.js:72-77`

The intended Phase B implementation path is a JS parity-proof test/control surface, not a production-loop reduction. Bridge Round 1 reproduced that the staged write set has no runtime/substrate executable delta and no L4 gate file, so the honest final package classification is `L4_ENABLER`, not `L4_STRUCTURAL`.

- `reports/deferred/non_blocking/n3-kernel-driver-js-fuel-threading-parity-proof-2026-05-20_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Re-ground the wave from `TASKS.md:395` and the prerequisite packet at `reports/control_plane/n3-kernel-driver-js-fuel-threading-parity-prereq-2026-05-20_2026-05-20.md:57-120`.
2. Implement or select the D006 JavaScript linked-list fuel-threading parity proof before any production `max_steps` host-loop reduction.
3. Compare the JS proof against Python D006 behavior in `tests/research/test_d006_h1_fuel_threading.py:40-127` and `tests/research/test_d006_h1_fuel_threading.py:181-411`, including Mu linked-list fuel shape, one-node-per-step consumption, zero-fuel behavior, status taxonomy `ok`/`stall`/`fuel_exhausted`, state sequence, final state, reason, and remaining fuel counts.
4. Include negative controls grounded in `tests/research/test_d007_h3_negative_control.py:137-363` for single step, fixed unroll, recursion, and higher-order composition limits.
5. Reuse existing JavaScript parity harness patterns from `mu/tests/parity/test_js_parity_automated.py:37-94` and `mu/tests/parity/test_exhaustion_parity.py:211-330` where current code truth supports reuse.
6. Lock focused Phase B validation around the D006 JS parity proof, Python D006 reference, D007 negative controls, host-semantics ratchet, host-authority ratchet, and docs consistency.
7. Preserve the post-PR #1004 ratchet boundary from `TASKS.md:395`: JS `host_builtin=2 host_iteration=1 host_mutation=0 host_recursion=0` and Python `host_builtin=1 host_iteration=1 host_mutation=0 host_recursion=0`; no increase is permitted in this prerequisite proof wave.

## Constraints

- Do not edit production `max_steps` loops or claim production loop reduction in this wave.
- Do not edit runtime/substrate files merely to satisfy `L4_STRUCTURAL`; this prerequisite proof is bounded to parity/control evidence.
- Preserve production loop truth references at `mu/host/python/rcx_pi/selfhost/step_mu.py:1163-1172`, `mu/host/python/rcx_pi/selfhost/step_mu.py:1317-1319`, and `mu/host/js/engine/kernel.js:72-77`.
- Do not edit ratchet baselines, marker files, answer tables, commit automation, dispatcher surfaces, `TASKS.md`, `STATUS.md`, `CHANGELOG.md`, `reports/README.md`, or unrelated reports as part of this Phase A rewrite.
- Do not use host timers, host exception tables, thread-state checks, substrate-specific shortcuts, host-only accepted sets, or comment-only green status to satisfy the proof.
- Do not inspect or modify unrelated dirty files, unrelated executor/test changes, or broad repo state for this packet rewrite.

## Stop Conditions

- Stop before Phase B implementation if the proof would require files outside the bounded Phase B scope or any forbidden host shortcut listed above.
- Stop if current code truth proves the D006 JS linked-list fuel parity proof is already implemented; remove it from pending work and rewrite the acceptance criteria around evidence-only validation instead of relisting it as unresolved.
- Stop if the focused parity command cannot be locked to D006 JS parity, Python D006 reference behavior, and D007 negative controls without widening into unrelated suites.
- Stop if host-semantics or host-authority ratchets would increase, or if a claimed reduction lacks direct ratchet output and production-loop evidence after Phase B.
- Stop if the work would require production `max_steps` loop edits, ratchet baseline edits, marker changes, or any production-loop reduction claim.

## Acceptance Criteria

- The packet carries explicit bounded scope, work items, constraints, stop conditions, acceptance criteria, and grounding/authorization sections.
- Same-wave authorization is mechanically detectable from this packet via `FOUNDER_OVERRIDE:n3-kernel-driver-js-fuel-threading-parity-proof-2026-05-20`.
- Phase B either implements/selects the JS linked-list fuel parity proof in `mu/tests/parity/test_exhaustion_parity.py` or proves current code already satisfies it and removes redundant pending implementation wording.
- The JS proof matches Python D006 behavior for Mu linked-list fuel shape, one-node-per-step consumption, zero-fuel behavior, status taxonomy `ok`/`stall`/`fuel_exhausted`, state sequence, final state, reason, and remaining fuel counts.
- D007 negative controls cover single step, fixed unroll, recursion, and higher-order composition limits without host-only shortcuts.
- Focused validation passes:
  - `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/parity/test_exhaustion_parity.py -k d006 --tb=short`
  - `python3 mu/tools/checks/check_host_semantics_ratchet.py --json`
  - `python3 tools/checks/check_host_authority_inventory_ratchet.py`
  - `./tools/checks/check_docs_consistency.sh`
- Ratchet evidence shows no host-semantics increase from the `TASKS.md:395` before-state, and host-authority inventory shows no unaccepted new authority increase.
- Production `max_steps` loop references remain unchanged, and the wave makes no production-loop reduction claim.
- Final write-set classification is `L4_ENABLER`: direct staged contract evidence for Bridge Round 1 showed `Runtime files: 0`, no changed `tests/l4_gates/` or `mu/tests/l4_gates/` file, and a missing indicator artifact, while the implemented proof is confined to `mu/tests/parity/test_exhaustion_parity.py` plus same-wave tracker/indicator control surfaces.

## Grounding / Authorization

- `TASKS.md:395` authorizes this wave as `[NEXT-CODEX-POST-REDTEAM] - D006 JavaScript fuel parity proof route`, `target_gate_id: G8`, `workload_target: host_debt_reduction`, with packet path `reports/control_plane/n3-kernel-driver-js-fuel-threading-parity-proof-2026-05-20_2026-05-20.md`; Bridge Round 1 reclassifies the package to `L4_ENABLER` because the current code truth is test/control-surface proof only.
- `TASKS.md:395` states the prerequisite proof must not increase host-semantics counts and that any claimed reduction requires direct ratchet output and production-loop evidence after Phase B.
- `TASKS.md:395` names structural artifacts `mu/tests/parity/test_exhaustion_parity.py`, `tests/research/test_d006_h1_fuel_threading.py`, `tests/research/test_d007_h3_negative_control.py`, and `mu/host/js/engine/kernel.js`.
- `TASKS.md:395` grounds the predecessor dependency: PR #1004 completed the source-proof prerequisite only; production `max_steps` loop reduction remains locked behind JS D006 fuel parity, performance, and integration prerequisites.
- Governing prerequisite packet: `reports/control_plane/n3-kernel-driver-js-fuel-threading-parity-prereq-2026-05-20_2026-05-20.md:57-120`, with lines 57-71 defining Mu-data linked-list fuel semantics and lines 101-120 enumerating minimum parity and negative-control proof classes.
- FOUNDER_OVERRIDE:n3-kernel-driver-js-fuel-threading-parity-proof-2026-05-20

Routed next-candidate:
n3-kernel-driver-js-fuel-threading-parity-proof-2026-05-20

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `n3-kernel-driver-js-fuel-threading-parity-proof-2026-05-20`
- Active packet: `reports/control_plane/n3-kernel-driver-js-fuel-threading-parity-proof-2026-05-20_2026-05-20.md`
- Indicator artifact: `reports/l4_wave_indicators/n3-kernel-driver-js-fuel-threading-parity-proof-2026-05-20.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/tests/parity/test_exhaustion_parity.py`
  - `reports/control_plane/n3-kernel-driver-js-fuel-threading-parity-proof-2026-05-20_2026-05-20.md`
  - `reports/deferred/non_blocking/n3-kernel-driver-js-fuel-threading-parity-proof-2026-05-20_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/n3-kernel-driver-js-fuel-threading-parity-proof-2026-05-20.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `n3-kernel-driver-js-fuel-threading-parity-proof-2026-05-20`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/n3-kernel-driver-js-fuel-threading-parity-proof-2026-05-20_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `n3-kernel-driver-js-fuel-threading-parity-proof-2026-05-20`
- Active packet: `reports/control_plane/n3-kernel-driver-js-fuel-threading-parity-proof-2026-05-20_2026-05-20.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `a8039dcd493eaac810567de9b0f9d172aa182a815082d0be161f1dce50b5e62a`
- Indicator artifact: `reports/l4_wave_indicators/n3-kernel-driver-js-fuel-threading-parity-proof-2026-05-20.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/parity/test_exhaustion_parity.py -k d006 --tb=short`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/n3-kernel-driver-js-fuel-threading-parity-proof-2026-05-20_2026-05-20.md. (2) Final pytest gate covered 1 existing parity test file from the wave-owned diff, consolidating the D006 JS fuel proof into `mu/tests/parity/test_exhaustion_parity.py` so growth caps and affected-file commit timeouts remain satisfied. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/n3-kernel-driver-js-fuel-threading-parity-proof-2026-05-20.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/parity/test_exhaustion_parity.py`
  - `reports/control_plane/n3-kernel-driver-js-fuel-threading-parity-proof-2026-05-20_2026-05-20.md`
  - `reports/deferred/non_blocking/n3-kernel-driver-js-fuel-threading-parity-proof-2026-05-20_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/n3-kernel-driver-js-fuel-threading-parity-proof-2026-05-20.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
