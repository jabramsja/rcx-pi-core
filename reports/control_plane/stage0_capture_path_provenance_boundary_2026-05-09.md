# Stage0 Capture Path Provenance Boundary

Date: 2026-05-10
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: stage0-capture-path-provenance-boundary-2026-05-09
Phase-A-Lock: LOCKED
Class: L4_ENABLER
Category: /mu structural Stage0 boundary
Source authorization: TASKS.md:512 FOUNDER_OVERRIDE:stage0-capture-path-provenance-boundary-2026-05-09; routed-by-repo-truth-mu-structural-advisory-triage-2026-05-09
Routing source: reports/control_plane/repo_truth_mu_structural_advisory_triage_2026-05-09.md
## Scope

- Deduplicated source advisories:
  - `reports/deferred/non_blocking/redteam_2026-03-14_repo_non_blockers.md` N1
  - `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md` N14
- Evidence surfaces:
  - `mu/host/python/rcx_pi/selfhost/stage0_vm.py`
  - `mu/host/js/core/stage0_vm.js`
  - focused Stage0 VM direct-API tests under `mu/tests/`

- `reports/deferred/non_blocking/stage0-capture-path-provenance-boundary-2026-05-09_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work Items

1. Reproduce that `capture_path` stores the raw resolved value before
   `capture_ref` materialization canonicalizes non-Mu hostile leaves to
   `None`/`null`.
2. Decide whether the correct structural boundary is capture-time Mu validation,
   capture-time safe copy/canonicalization, or an explicit provenance rule for
   direct Stage0 API inputs.
3. If implementation is warranted, define a later Phase B scope that updates
   Python and JavaScript Stage0 behavior together and proves parity with focused
   direct-API tests.

## Phase A Result

Status: reproduced, implementation warranted, runtime edits not authorized by
this packet.

Current direct-API behavior still reproduces the routed advisory:

- Python `capture_path` resolves an `EvilStr` leaf from a plain input dict and
  `capture_ref` materialization canonicalizes the captured non-Mu leaf to
  `None`. Direct output: `match / NoneType / False / None`.
- JavaScript `capture_path` resolves a `String` object leaf from a plain input
  object and `capture_ref` materialization canonicalizes the captured non-Mu
  leaf to `null`. Direct output: `match / false / true / null`.

Additional direct boundary probe:

- Python `_resolve_path({"x": EvilStr("tainted")}, ["focus", "root", "x"])`
  returns the raw `EvilStr`; `_safe_mu_copy(...)` then returns `None`.
- JavaScript `resolvePath({ x: new String("tainted") }, ["focus", "root",
  "x"])` returns the raw `String` object; `muCopy(...)` then returns `null`.

The source path remains the same on both substrates: `capture_path` stores
`captures[name] = val` before the later `capture_ref` materialization path calls
`_safe_mu_copy` / `safeMuCopy`.

## Boundary Decision

The correct later implementation boundary is capture-time Mu validation with a
safe copy only after validation succeeds.

- Plain capture-time safe copy alone is rejected because the current copy helper
  canonicalizes non-Mu leaves to `None` / `null`, which would keep converting
  arbitrary direct-API host artifacts into valid Mu output.
- A documentation-only provenance rule is insufficient because it leaves the
  direct Stage0 API accepting raw host artifacts into VM capture state.
- Capture-time validation should fail closed before a value enters `captures`.
  After validation succeeds, storing a Stage0-owned safe copy narrows the direct
  API bootstrap boundary without adding host-only object semantics.

Production exploit claims remain excluded. The reproduced evidence is direct
Stage0 API behavior; current production callers were not shown to pass hostile
host leaves into the VM-backed kernel path.

## Later Phase B Scope

Exact runtime write set for a separate implementation packet:

- `mu/host/python/rcx_pi/selfhost/stage0_vm.py`
- `mu/host/js/core/stage0_vm.js`

Exact focused test write set for that later packet:

- `mu/tests/l4_gates/test_stage0_vm.py`
- one existing JS parity or L4 gate test surface under `mu/tests/` that can
  construct JavaScript host objects directly in Node.

Required later behavior proof:

- Valid Mu captures still match and materialize identically on Python and JS.
- Non-Mu direct-API capture leaves fail closed at `capture_path` instead of
  matching and returning `None` / `null`.
- The Python and JS failure mode is intentionally paired and does not rely on
  Python-only subclass semantics or JavaScript-only host object or Proxy
  semantics.
- No seeds, scheduler, registry, production callers, or unrelated runtime
  surfaces are touched.

## Constraints

- No Stage0 runtime edits in Phase A.
- No Python-only or JS-only remediation. Any later implementation must preserve
  cross-substrate Stage0 behavior.
- Do not add host-only object semantics. The fix must narrow the direct Stage0
  bootstrap boundary by validating, copying, or tagging Mu/provenance at the
  capture boundary.
- Do not alter production callers unless Phase A proves production exploitability.
- Do not edit Claude-related files.

## Stop Conditions

- Stop if current direct-API evidence no longer reproduces.
- Stop if the proposed fix would canonicalize arbitrary host objects into valid
  Mu by policy rather than fail-closing or preserving provenance.
- Stop if the implementation would touch seeds, scheduler, registry, or
  unrelated runtime surfaces.

## Acceptance Criteria

- Phase A records one canonical Stage0 capture advisory and does not route
  duplicate N14/N1 packets.
- Any later implementation packet states the exact Python/JS Stage0 write set,
  parity tests, and how the boundary narrows bootstrap debt without adding
  host-only semantics.
- Production exploit claims remain excluded unless reproduced.

## Validation Used

- `python3 - <<'PY' ... stage0_vm_step(capture_ref repro) ... PY` exited 0
  with `match / NoneType / False / None`.
- `node - <<'JS' ... stage0VmStep(capture_ref repro) ... JS` exited 0 with
  `match / false / true / null`.
- `python3 - <<'PY' ... _resolve_path + _safe_mu_copy probe ... PY` exited 0
  with `True / True / EvilStr / NoneType / None`.
- `node - <<'JS' ... resolvePath + muCopy probe ... JS` exited 0 with
  `true / true / [object String] / true / null`.

## Grounding / Authorization

- Source advisories:
  `reports/deferred/non_blocking/redteam_2026-03-14_repo_non_blockers.md` and
  `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md`.
- Routing triage:
  `reports/control_plane/repo_truth_mu_structural_advisory_triage_2026-05-09.md`.
- TASKS authorization:
  `TASKS.md:512` authorizes `[NEXT-CODEX-POST-REDTEAM]` for this packet as
  `Class: L4_ENABLER`, Category: `/mu` structural Stage0 boundary,
  `target_gate_id: G8`, and `workload_target: stage0_boundary`.
- Authorization:
  Same-wave `FOUNDER_OVERRIDE:stage0-capture-path-provenance-boundary-2026-05-09`
  from `TASKS.md:512`, plus the
  repo-truth-mu-structural-advisory-triage-2026-05-09 routing packet.
  This authorizes routed Phase A planning only; it does not authorize Stage0
  implementation edits.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `stage0-capture-path-provenance-boundary-2026-05-09`
- Active packet: `reports/control_plane/stage0_capture_path_provenance_boundary_2026-05-09.md`
- Indicator artifact: `reports/l4_wave_indicators/stage0-capture-path-provenance-boundary-2026-05-09.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `reports/control_plane/stage0_capture_path_provenance_boundary_2026-05-09.md`
  - `reports/deferred/non_blocking/stage0-capture-path-provenance-boundary-2026-05-09_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/stage0-capture-path-provenance-boundary-2026-05-09.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `stage0-capture-path-provenance-boundary-2026-05-09`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/stage0-capture-path-provenance-boundary-2026-05-09_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `stage0-capture-path-provenance-boundary-2026-05-09`
- Active packet: `reports/control_plane/stage0_capture_path_provenance_boundary_2026-05-09.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `d6d321beddc9f1c922d6440ebe9539922fcdafaee300a6b09a290c9112b21f80`
- Indicator artifact: `reports/l4_wave_indicators/stage0-capture-path-provenance-boundary-2026-05-09.json`
- Evidence command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id stage0-capture-path-provenance-boundary-2026-05-09 --output reports/l4_wave_indicators/stage0-capture-path-provenance-boundary-2026-05-09.json`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/stage0_capture_path_provenance_boundary_2026-05-09.md. (2) Commit handoff carries 4 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/stage0-capture-path-provenance-boundary-2026-05-09.json`
- Current staged files:
  - `TASKS.md`
  - `reports/control_plane/stage0_capture_path_provenance_boundary_2026-05-09.md`
  - `reports/deferred/non_blocking/stage0-capture-path-provenance-boundary-2026-05-09_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/stage0-capture-path-provenance-boundary-2026-05-09.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
