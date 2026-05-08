# Founder Ordered Redteam Mu Structural Blocking Remediation

Date: 2026-05-06
Plan rewrite date: 2026-05-08
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06
Phase-A-Lock: LOCKED
Class: L4_STRUCTURAL
Category: /mu structural
Severity: BLOCKING
Source audit packet: `reports/deferred/blocking/founder_ordered_redteam_repo_code_audit_2026-05-05_blocking.md`
Founder override: FOUNDER_OVERRIDE:founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06
Source queue override: FOUNDER_OVERRIDE:founder-ordered-redteam-remediation-queue-organization-2026-05-05

This packet is the Phase A remediation plan for the blocking `/mu` structural
finding `B1 - JavaScript Mu Validation Admits Host Objects`. It supersedes the
earlier queue-only packet text for this wave and is implementation-ready only
for the bounded scope below.
## Scope: Files/Directories In Scope

- `mu/host/js/core/types.js`
  - Primary implementation surface.
  - Tighten `isValidMu` in both the default integer-depth path and the
    structural-budget path so JavaScript host objects cannot pass as portable Mu
    records.
  - Keep `muHash`, `muHashCached`, `muHashControl`, and
    `muHashControlCached` fail-closed through the validator boundary rather than
    adding hash-only host-object special cases.
- `mu/host/js/core/bootstrap_core.js`
  - Same-wave Bridge Round 1 repair surface only for exported `match()` with
    a structural depth budget.
  - Enforce the same depth-zero Mu validation boundary before budgeted match
    recursion that default `match()` already enforced before key enumeration.
  - Do not change trusted kernel, Stage0, scheduler, seed, or host serialization
    behavior.
- `mu/host/python/rcx_pi/selfhost/mu_type.py`
  - Read-only parity reference for the exact compound-type boundary.
  - Edit only if focused implementation evidence proves a current Python/JS
    parity defect that cannot be resolved in the JavaScript boundary alone.
- `mu/tests/`
  - Focused proof surface for JavaScript Mu validation/hash fail-closed behavior
    and Python/JavaScript parity at the Mu boundary.
  - Add or update only the narrow test file(s) needed for this validator/hash
    boundary; do not refactor unrelated runtime, scheduler, seed, registry, or
    docs tests.
- `TASKS.md`
  - Tracker sync surface after implementation evidence exists.
  - Update only the `[FOUNDER-ORDERED-REDTEAM-MU-STRUCTURAL-BLOCKING-REMEDIATION]`
    entry under `[NEXT-CODEX-POST-REDTEAM]` with implementation status, focused
    evidence, and this same-wave founder override.
- `reports/control_plane/founder_ordered_redteam_mu_structural_blocking_remediation_2026-05-06.md`
  - Governing packet for this bounded Phase A wave.
- `mu/tools/executors/phase_b_executor.py`
  - Same-wave mechanical pipeline repair only if dispatcher/supervisor package
    truth blocks this structural remediation after implementation.
  - Keep the repair bounded to package governance propagation; do not widen into
    unrelated executor behavior.
- `mu/tests/tools/test_phase_b_executor.py`
  - Focused regression for the same-wave mechanical pipeline repair above.
- `mu/tools/executors/commit_executor.py`
  - Same-wave mechanical pipeline repair only for pre-commit failure state
    demotion before any local `git_commit` exists.
  - Keep the repair bounded to packet/TASKS control-plane state so dispatcher
    can re-enter after a failed pre-commit repair; do not add host semantics.
- `mu/tests/tools/test_commit_executor_receipt.py`
  - Focused regression for the commit-executor pending-state demotion above.
- `mu/tools/executors/executor_dispatch.py`
  - Same-wave mechanical pipeline repair only for founder-ordered routing
    records whose bounded candidate omits `tracked_packet`.
  - Derive the canonical packet from the matching `TASKS.md` queue entry before
    completed-state checks or Phase A plan-name selection.
- `mu/tests/tools/test_executor_dispatch.py`
  - Focused regression for the dispatcher missing-`tracked_packet` repair above.

## Work Items: Concrete Bounded Tasks From TASKS.md Current Phase

1. Reconfirm current code truth at implementation start for the exact finding
   inventory named in `TASKS.md` under `[NEXT-CODEX-POST-REDTEAM]`: JavaScript
   `Date`, `Map`, empty class instances, class instances with enumerable keys,
   and prototype-bearing host objects must not be accepted or hashed as Mu.
   If current code truth already rejects all audited JavaScript host-object
   cases, stop implementation and update the tracker as code-closed instead of
   relisting stale work.
2. Tighten `mu/host/js/core/types.js` so the `typeof value === "object"` branch
   accepts only the chosen portable JavaScript representation for JSON object
   records after arrays are handled. The chosen rule must reject `Date`, `Map`,
   class instances, objects with custom prototypes, and other host objects
   before key enumeration or recursive value validation.
3. Apply the same object-boundary rule consistently in both `isValidMu` paths:
   the default integer-depth path and the structural-budget path. Preserve
   existing width, symbol-key, string-key, cycle, depth, and budget behavior for
   values that remain valid portable Mu.
4. Preserve hashing by boundary tightening, not by host-object canonicalization:
   audited host objects must cause `muHash`/cached/control hash entry points to
   reject through `isValidMu`, and must no longer hash as `{}` or collide with
   plain Mu records such as `{"a": 1}`.
5. Add or update focused proof under `mu/tests/` and/or direct-output evidence
   that covers:
   - JavaScript rejection for `Date`, `Map`, empty class instance, class
     instance with enumerable key, and custom-prototype object inputs.
   - JavaScript hash failure for those same rejected inputs.
   - Continued JavaScript acceptance and stable hashing for portable Mu
     primitives, arrays, and plain JSON object records.
   - Continued Python rejection of arbitrary objects and `dict` subclasses, with
     plain dict/list behavior remaining the parity reference.
6. Run focused validation only for the Mu validator/hash boundary and record the
   commands and outputs needed to prove the acceptance criteria.
7. Update the `TASKS.md` tracker entry for this wave after implementation with
   implementation status, files changed, evidence commands/results, and
   `FOUNDER_OVERRIDE:founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06`.

## Constraints: What Is Not In Scope

- Do not work on the sibling non-blocking `/mu` structural packet.
- Do not rerun or rewrite the founder-ordered repo-code, docs, tests, or tooling
  audits.
- Do not relist already landed engine-state/scheduler seed, fixture,
  structural-test, scheduler-parity, or seed-registration work as unresolved.
- Do not change `/mu` runtime, Stage0, scheduler, seed registry, projection,
  engine pipeline, CLI, or ontology-evidence behavior unless a focused validator
  dependency proves it is required for this exact boundary defect.
- Do not add host-specific serialization semantics for `Date`, `Map`, class
  instances, custom prototypes, or other JavaScript object-model values.
- Do not change Python Mu semantics unless JavaScript-only remediation cannot
  preserve the documented Python/JavaScript parity boundary.
- Do not edit Claude-related files or home-directory surfaces.
- Do not update documentation, indexes, reports, or trackers other than the
  scoped `TASKS.md` implementation evidence entry after the code proof exists.
- Same-wave pipeline repair is in scope only for a reproduced dispatcher or
  supervisor packaging failure that blocks this exact structural remediation,
  and must be paired with a focused regression before dispatcher rerun.

## Stop Conditions

- Stop before code edits if the focused current-code probe proves JavaScript
  already rejects every audited host-object case through both validation and
  hashing.
- Stop if the proposed implementation would make host objects portable by
  canonicalizing, serializing, copying, or otherwise translating them into Mu.
- Stop if the object-boundary rule would reject ordinary portable JSON object
  records without an explicit source packet narrowing the JavaScript Mu
  representation.
- Stop if the fix would preserve default-path behavior but leave the
  structural-budget path accepting host objects, or vice versa.
- Stop if Python/JavaScript parity for valid portable Mu values or documented
  rejection cases cannot be preserved.
- Stop if the implementation requires edits outside the explicit scope above.
- Stop if any Claude-related file would need to be edited.

## Acceptance Criteria

- `isValidMu` in JavaScript rejects the audited host-object cases: `Date`,
  `Map`, empty class instance, class instance with enumerable key, and
  custom-prototype/prototype-bearing host objects.
- `muHash`, `muHashCached`, `muHashControl`, and `muHashControlCached` reject
  those same cases through the Mu validator boundary and no longer hash them as
  `{}` or as equivalent to plain Mu records.
- Both JavaScript validation paths, the default integer-depth path and the
  structural-budget path, enforce the same host-object rejection boundary.
- Portable Mu values remain accepted and hash-compatible for JSON-native
  primitives, arrays, and plain object records within the existing depth, width,
  key, symbol, and cycle limits.
- Python remains the parity reference for exact `list`/`dict` compound types:
  arbitrary objects and `dict` subclasses are rejected, while plain dict/list Mu
  values remain accepted.
- Focused direct-output evidence and/or focused tests prove the formerly
  accepted JavaScript host-object cases fail closed.
- The wave does not relist already landed engine-state/scheduler seed, fixture,
  structural-test, scheduler-parity, or seed-registration work as unresolved.
- `TASKS.md` is updated after implementation with status, evidence commands and
  results, files changed, and the same-wave founder override for this wave.

## Grounding / Authorization

- `TASKS.md:439` marks `[NEXT-CODEX-POST-REDTEAM]` as unparked and
  founder-authorized.
- `TASKS.md:443` states that engine-state/scheduler seed, fixture,
  structural-test, scheduler-parity, and seed-registration work has already
  landed and must not be relisted as unresolved.
- `TASKS.md:447` orders the founder redteam remediation queue by category and
  severity, with `/mu` structural remediation last in the queue.
- `TASKS.md:459` names this exact wave, class, category, packet path, source
  audit packet, and finding inventory for `B1 - JavaScript Mu Validation Admits
  Host Objects`.
- The source audit packet
  `reports/deferred/blocking/founder_ordered_redteam_repo_code_audit_2026-05-05_blocking.md`
  preserves the original defect evidence:
  - Lines 36-43: JavaScript accepts any `typeof === "object"` value before key
    validation, with no plain-object or prototype restriction.
  - Lines 44-51: Python defines Mu as JSON-compatible and requires exact
    `list`/`dict` compound types.
  - Lines 55-98: direct JavaScript/Python output proves the JS/Python boundary
    mismatch for host objects and subclasses.
- Implementation code truth after pre-push purity correction removes the
  host-oracle Proxy detector and narrows the claim to structural fail-closed
  inspection:
  - `mu/host/js/core/types.js` keeps only the existing Node `crypto` boundary.
  - `mu/host/js/core/types.js` wraps object and array structural inspection so
    hostile/trapping JavaScript host artifacts fail closed in both `isValidMu`
    paths without adding a new stdlib import.
  - Transparent JavaScript Proxy rejection is not claimed here because pure
    structural reflection cannot distinguish `new Proxy({a: 1}, {})` from its
    target without invoking a host proxy oracle.
  - `mu/host/js/core/types.js:281` through `mu/host/js/core/types.js:365`
    keep `muHash`, `muHashCached`, `muHashControl`, and
    `muHashControlCached` behind the validator boundary.
  - `mu/host/python/rcx_pi/selfhost/mu_type.py:203` through
    `mu/host/python/rcx_pi/selfhost/mu_type.py:251` remains the read-only exact
    compound-type parity reference for Python Mu.
- Current direct probes during re-entry show hostile/trapping Proxy values,
  BigInt, object host artifacts, array host artifacts, and hidden-key artifacts
  reporting `defaultValid:false`, `budgetValid:false`, and all four JS hash
  entry points returning `input.invalid_type`, while plain records remain valid
  and hashable; Python still rejects arbitrary objects and `dict` subclasses.
- Same-wave control-plane implementation authorization:
  FOUNDER_OVERRIDE:founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06`
- Active packet: `reports/control_plane/founder_ordered_redteam_mu_structural_blocking_remediation_2026-05-06.md`
- Indicator artifact: `reports/l4_wave_indicators/founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/host/js/core/bootstrap_core.js`
  - `mu/tests/l4_gates/test_d009_production_depth_gate.py`
  - `mu/tests/parity/test_js_parity_automated.py`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/founder_ordered_redteam_mu_structural_blocking_remediation_2026-05-06.md`
  - `reports/deferred/non_blocking/founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

## Same-Wave Pipeline Repair (2026-05-08)

- Reproduced blocker: post-reentry pre-commit supervisor rejected the package
  because `.scratch/phase_b_supervisor_package.json` declared
  `wave_class: L4_ENABLER` while the locked packet, TASKS tracker, and staged
  runtime diff classify this wave as `L4_STRUCTURAL`.
- Root-cause evidence: `mu/tools/executors/phase_b_executor.py` refreshed
  re-entry package `changed_files`, `scope_items`, `bridge_status`, evidence
  handles, blocker acknowledgments, and override-token state, but did not refresh
  `supervisor_package["wave_class"]` from the live packet before writing the
  re-entry package.
- Mechanical fix: re-entry supervisor package refresh now assigns
  `supervisor_package["wave_class"] = wave_class` after live packet governance
  refresh and before package write.
- Regression: `mu/tests/tools/test_phase_b_executor.py::TestMaintenanceTrackerMetadataPropagation::test_reentry_supervisor_package_refreshes_wave_class_from_live_packet`
  models the stale `L4_ENABLER` initial package followed by a live
  `L4_STRUCTURAL` re-entry packet and asserts the re-entry package is structural
  with no `founder_override_token`.
- Local evidence: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_phase_b_executor.py::TestMaintenanceTrackerMetadataPropagation::test_reentry_supervisor_package_refreshes_wave_class_from_live_packet`
  exits `0` with `1 passed in 4.34s`; the broader focused Phase B package set
  exits `0` with `4 passed in 13.04s`; `python3 -m py_compile
  mu/tools/executors/phase_b_executor.py mu/tools/executors/recovery_gate.py`
  exits `0`.

## Re-entry Host-Oracle Purity Correction (2026-05-08)

- Reproduced blocker: pre-push purity rejected the staged Node `util` import
  used only for `util.types.isProxy` as a new JavaScript kernel stdlib import.
- Root-cause evidence: `mu/host/js/core/types.js` imported
  `const { types: utilTypes } = require('util');`, and pre-push-fast reported
  `FAIL: NEW stdlib/Node.js imports in JavaScript kernel: ['util']`.
- Mechanical fix: `mu/host/js/core/types.js` removes the host proxy oracle and
  wraps structural array/object inspection in a fail-closed boundary, so
  BigInt and hostile/trapping host artifacts reject through `isValidMu` without
  expanding JS kernel authority.
- Regression: `mu/tests/l4_gates/test_d009_production_depth_gate.py` and
  `mu/tests/parity/test_js_parity_automated.py` cover BigInt, throwing object
  Proxies, throwing array Proxies, and trap-shaped Proxies across default
  validation, structural-budget validation, and all four hash entry points.
- Deferred boundary: transparent JavaScript Proxy rejection remains
  non-blocking/policy-bound because it requires either structural provenance or
  an explicit host-oracle override.
- Local evidence: direct JS re-entry probe reports BigInt and hostile/trapping
  Proxy cases as `defaultValid:false`, `budgetValid:false`, and
  `input.invalid_type` for `muHash`, `muHashCached`, `muHashControl`, and
  `muHashControlCached`; `PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_d009_production_depth_gate.py::TestJSMuHostObjectBoundaryGate::test_js_host_artifacts_reject_before_budget_or_hash_semantics --tb=short && PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/parity/test_js_parity_automated.py -k "host_artifacts or poisoning_cache or exact_compound_boundary" --tb=short` exits `0` with `1 passed` plus `3 passed, 302 deselected`.

## Pre-Commit Growth-Cap Repair (2026-05-08)

- Reproduced blocker: commit executor Step 8 failed in `pre-commit-doc-check`
  because `tests/docs/test_growth_caps.py::TestGrowthCaps::test_test_file_count_within_cap`
  reported `Test file count (314) exceeds baseline (190) + cap (122) = 312`.
- Root-cause evidence: the staged package had added two new `test_*.py` files,
  exactly matching the over-cap delta.
- Repair: the host-object boundary tests were consolidated into existing
  `mu/tests/l4_gates/test_d009_production_depth_gate.py` and
  `mu/tests/parity/test_js_parity_automated.py`, and the two new test files were
  removed from the staged wave. This preserves the proof without requesting a
  growth exception or widening host semantics.
- Mechanical enforcement: no new automation is required for this class of
  failure because the existing pre-commit growth-cap gate caught it before
  commit; the same gate is rerun after consolidation.

## Commit-Retry State Demotion Repair (2026-05-08)

- Reproduced blocker: after the growth-cap consolidation changed the staged
  content, `pre-commit-doc-check` passed docs consistency and governance tests
  but failed the receipt check as stale; a direct dispatcher Phase B re-entry
  then stopped with `Refusing to dispatch an already-complete bounded candidate`
  because this packet still declared `Status: COMPLETED (commit-ready,
  supervisor COMMIT_GO)`.
- Root-cause evidence: `phase_b_executor.py` advances the packet status to
  completed at commit-ready before `commit_executor.py` has created a local
  commit, while `executor_dispatch.py` stops on completed packet status and
  completed `TASKS.md` queue state before invoking Phase B.
- Mechanical fix: `commit_executor.py` now demotes the tracked control-plane
  packet status and matching founder-ordered `TASKS.md` queue state to
  `IMPLEMENTED - PIPELINE REPAIR PENDING COMMIT` whenever commit execution
  returns `status:error` before `git_commit`. It stages both demotions so the
  next dispatcher run can re-enter Phase B for a fresh supervisor receipt.
- Regression: `mu/tests/tools/test_commit_executor_receipt.py::TestReceiptChainEndToEnd::test_pre_commit_failure_demotes_completed_packet_and_task_for_dispatch_retry`
  models a completed packet plus completed founder queue state and a
  `run_pre_commit_script` failure before `git_commit`, then asserts both
  surfaces are demoted and staged for dispatcher re-entry.
- Local evidence: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py::TestReceiptChainEndToEnd::test_pre_commit_failure_demotes_completed_packet_and_task_for_dispatch_retry --tb=short`
  exits `0` with `1 passed in 0.27s`; `python3 -m py_compile
  mu/tools/executors/commit_executor.py` exits `0`.

## Commit-Retry Receipt Invalidation Repair (2026-05-08)

- Reproduced blocker: Phase B final pytest failed in
  `mu/tests/tools/test_executor_dispatch.py::TestReceiptAndCommit::test_commit_path_refresh_persists_handoff_scope_and_fresh_receipt`
  because commit-retry state demotion changed the staged packet after the fresh
  supervisor receipt was minted, leaving the durable Phase B handoff pointing at
  a receipt for the pre-demotion staged SHA.
- Root-cause evidence: the isolated test reported receipt `staged_sha`
  `0c255fb9c29ee83f6e4030a3a93394132315892ff830333307e55dff0d7ce105`
  while the current staged diff SHA was
  `350e6ee69ae589a882182bf0e7e94129aa8e08aaaa856cb32db02ddbfe367224`;
  the mutation occurs after `run_commit_pipeline()` invokes the retry demotion
  hook on `status:error` before `git_commit`.
- Mechanical fix: `commit_executor.py` now clears stale
  `evidence_handles.pre_commit_receipt` from the durable Phase B handoff when
  retry demotion stages packet/TASKS changes, preserving the Phase B handoff
  receipt provenance path while forcing the next dispatcher/Phase B pass to mint
  a fresh supervisor receipt for the new staged package.
- Regression: `mu/tests/tools/test_commit_executor_receipt.py::TestReceiptChainEndToEnd::test_pre_commit_failure_demotes_completed_packet_and_task_for_dispatch_retry`
  now asserts the durable handoff receipt evidence is invalidated after retry
  demotion, and `mu/tests/tools/test_executor_dispatch.py::TestReceiptAndCommit::test_commit_path_refresh_persists_handoff_scope_and_fresh_receipt`
  asserts the commit path no longer preserves a stale fresh receipt handle after
  demotion changes staged scope.
- Local evidence: `PYTHONHASHSEED=0 python3 -m pytest -q
  mu/tests/tools/test_executor_dispatch.py::TestReceiptAndCommit::test_commit_path_refresh_persists_handoff_scope_and_fresh_receipt
  mu/tests/tools/test_commit_executor_receipt.py::TestReceiptChainEndToEnd::test_pre_commit_failure_demotes_completed_packet_and_task_for_dispatch_retry
  --tb=short` exits `0` with `2 passed in 2.18s`; `PYTHONHASHSEED=0 python3
  -m pytest -x --tb=short mu/tests/l4_gates/test_d009_production_depth_gate.py
  mu/tests/parity/test_js_parity_automated.py
  mu/tests/tools/test_commit_executor_receipt.py
  mu/tests/tools/test_executor_dispatch.py
  mu/tests/tools/test_phase_b_executor.py` exits `0` with `1292 passed in
  596.86s`.

## Dispatcher Missing-Tracked-Packet Repair (2026-05-08)

- Reproduced blocker: the canonical post-merge routing record for this wave had
  a bounded `next_candidates` entry with `candidate` and `bounded: true` but no
  `tracked_packet`; top-level dispatcher therefore entered Phase A with
  `--plan-name founder_ordered_redteam_mu_structural_blocking_rem`, which minted
  a duplicate date-slug packet instead of using the existing locked remediation
  packet.
- Root-cause evidence: `.agent_bus/meta/post_merge_routing.json` lacked
  `tracked_packet` in `next_candidates`, `phase_a_executor_live.log` showed the
  new draft path `reports/control_plane/founder_ordered_redteam_mu_structural_blocking_rem_2026-05-08.md`,
  and the duplicate file was untracked while the authorized packet remained
  `reports/control_plane/founder_ordered_redteam_mu_structural_blocking_remediation_2026-05-06.md`.
- Mechanical fix: `executor_dispatch.py` now enriches founder-ordered routing
  records by deriving a missing bounded candidate `tracked_packet` from the
  matching `TASKS.md` queue entry before completed-packet/task checks and Phase
  A plan-name selection.
- Regression: `mu/tests/tools/test_executor_dispatch.py::TestDispatcherFreshnessRefresh::test_dispatch_derives_missing_tracked_packet_from_founder_tasks_before_phase_a`
  proves Phase A receives the canonical packet stem instead of a candidate-slug
  duplicate when a founder queue record omits `tracked_packet`.
- Regression: `mu/tests/tools/test_executor_dispatch.py::TestDispatcherFreshnessRefresh::test_dispatch_stops_completed_tasks_state_even_when_record_lacks_tracked_packet`
  proves completed TASKS state still stops dispatch after the packet is derived
  from the founder queue entry.
- Local evidence: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_dispatch.py::TestDispatcherFreshnessRefresh::test_dispatch_derives_missing_tracked_packet_from_founder_tasks_before_phase_a mu/tests/tools/test_executor_dispatch.py::TestDispatcherFreshnessRefresh::test_dispatch_stops_completed_tasks_state_even_when_record_lacks_tracked_packet --tb=short`
  exits `0` with `2 passed in 0.84s`; `python3 -m py_compile
  mu/tools/executors/executor_dispatch.py mu/tests/tools/test_executor_dispatch.py`
  exits `0`.

## Bridge Round 1 Match-Budget Boundary Repair (2026-05-08)

- Reproduced blocker: exported JavaScript `match()` rejected hidden
  non-enumerable-key and custom-prototype host objects through the default path,
  but `match(..., _STRUCTURAL_DEPTH_BUDGET)` returned `{}` or variable bindings
  for those same invalid pattern/input values before invoking the depth-zero
  Mu validator.
- Root-cause evidence: `mu/host/js/core/bootstrap_core.js` had the default
  branch validate `pattern` and `input` at depth zero before normalized-dict
  handling and recursion, while the structural-budget branch consumed budget and
  entered `isVar`, `Array.isArray`, and `Object.keys` recursion first.
- Mechanical fix: the structural-budget branch now validates `pattern` and
  `input` once at the public depth-zero boundary using `isValidMu`, then marks
  recursive budget calls as validated so existing valid-Mu budget exhaustion
  still returns `NO_MATCH`.
- Regression: `mu/tests/l4_gates/test_d009_production_depth_gate.py::TestJSMuHostObjectBoundaryGate::test_js_host_artifacts_reject_before_budget_or_hash_semantics`
  and `mu/tests/parity/test_js_parity_automated.py::TestJSSecurityParity::test_js_mu_boundary_rejects_object_and_array_host_artifacts`
  now prove default and budgeted `match()` reject the audited host artifacts as
  both invalid patterns and invalid inputs while valid portable records still
  bind successfully.
- Local evidence: direct JS bridge repro now reports `hiddenPattern`,
  `hiddenInput`, `customPattern`, and `customInput` as
  `default:"input.invalid_type"` and `budget:"input.invalid_type"`, while
  `validPlain` returns `{x:1}` on both paths; `PYTHONHASHSEED=0 python3 -m
  pytest -q
  mu/tests/l4_gates/test_d009_production_depth_gate.py::TestJSMuHostObjectBoundaryGate::test_js_host_artifacts_reject_before_budget_or_hash_semantics
  --tb=short && PYTHONHASHSEED=0 python3 -m pytest -q
  mu/tests/parity/test_js_parity_automated.py -k "host_artifacts or
  poisoning_cache or exact_compound_boundary" --tb=short` exits `0` with
  `1 passed in 0.13s` plus `3 passed, 302 deselected in 0.32s`.
