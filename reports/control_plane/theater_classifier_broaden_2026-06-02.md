# Theater Classifier Broaden 2026-06-02

Date: 2026-06-02
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: theater-classifier-broaden-2026-06-02
Phase-A-Lock: LOCKED
Class: L4_ENABLER (tooling-only; touches no runtime dir)
target_gate_id: G8
Packet: reports/control_plane/theater_classifier_broaden_2026-06-02.md

Purpose: Broaden the theater-risk classifier `check_gate_behavioral_pairs.py` (the CLASSIFIER_SCRIPT that `check_theater_risk_ratchet.py` runs) so it stops mis-flagging two REAL-assertion patterns as theater_risk: (1) assertions made inside same-module helper functions a test calls — including `self`/`cls` method helpers such as `_check_js_function_boundary`, not just bare-name helpers, and (2) raises-on-failure validator calls where the call itself is the assertion. Following the helper call must also PRESERVE the helper's proof class: a helper that reads source keeps its test classified source_lock, never silently downgraded to behavioral. Helper resolution must be scope-correct: a `self`/`cls` call resolves ONLY against its enclosing class's methods (same-file classes reuse helper names such as `_js_eval`/`_run_js`/`_run_js_builder`), and any name that does not resolve uniquely within its proper scope is fail-closed (no recursion), never silently bound to an arbitrary later same-named helper from a different class. Classifier + regression tests only — no allowlist pruning.

## Scope

In scope (tooling-only, L4_ENABLER, no runtime dir touched):
- `tools/checks/check_gate_behavioral_pairs.py` — the only production file changed. Add the two bounded detectors below by editing `scan_file`, `classify_method`, `_has_meaningful_assertion`, and `_has_raise_or_subprocess`. READ those four functions before editing.
- The existing test file that covers `check_gate_behavioral_pairs` (the module matched by the `-k "gate_behavioral or theater"` selector under `mu/tests/`; Phase B resolves the exact existing file). Add the regression tests there. Do NOT create a new test file (avoids the test-count growth-cap bump).

- `reports/deferred/non_blocking/theater-classifier-broaden-2026-06-02_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

Concrete bounded tasks (the two precise detectors named in the TASKS.md tracker note for this wave, plus regression tests). Detector 1 carries the two fixes the bridge REQUEST_CHANGES flagged: (1a) explicit `ast.Attribute`/self-method callee normalization, and (1b) proof-class preservation through the recursion.

1. Helper-function assertions (detector 1). `_has_meaningful_assertion` currently walks only the test function's own body, so assertions inside same-module helper functions the test calls are missed → false theater_risk. The missed callers come in two callee forms: bare-name calls (`_source_step(...)`, `_run_js_vm(...)`, `_js_eval(...)` — callee is `ast.Name`) AND `self`/`cls` method calls (`self._check_js_function_boundary(...)` — callee is `ast.Attribute`), the latter being the form used by the four `TestJSOuterLoopBoundary.test_js_run_*_boundary` tests, which currently all classify theater_risk (verified via `check_gate_behavioral_pairs.py --json`). Fix:
   - **Scope-correct resolution maps (REQUEST_CHANGES fix — duplicate helper names).** In `scan_file`, do NOT build one flat global `{bare_name: FunctionDef}` map. The classifier's own scan set already contains same-file classes that reuse helper names: `_js_eval` is defined as a `self` method in five distinct classes of `test_terminal_classification_parity_gate.py` (`TestTerminalKeySetParity`, `TestEnumParity`, `TestJSCacheHardening`, `TestExitReasonCoercionParity`, `TestHemisphereSourceLock`), and `_run_js_builder` / `_run_js` are likewise duplicated across classes — so a flat map collapses each name to its LAST definition, and a `self._js_eval(...)` call in one class would resolve to a different class's helper and emit the wrong proof class. Instead build TWO scope-keyed structures: (i) a **module map** `{name: FunctionDef}` of module-level and lexically-nested `FunctionDef`s, used to resolve bare-name `ast.Name` calls (e.g. a module-level `_source_step`); and (ii) a **per-class method map** keyed by enclosing class (`{ClassDef: {method_name: FunctionDef}}`), so a `self`/`cls` method call (e.g. `_check_js_function_boundary`) resolves ONLY against the methods of the test's own enclosing class. Thread both maps — plus the enclosing class of the function currently being scanned — into `classify_method` and the recursion.
   - **(1a) Callee normalization + scoped lookup — first REQUEST_CHANGES fix.** For each `ast.Call` in the test body, recover the candidate helper name from BOTH callee forms: `ast.Name` callee → `func.id`; `ast.Attribute` callee whose `.value` is an `ast.Name` with id in `{self, cls}` → `func.attr`. Then resolve the recovered name in the form-appropriate scope and recurse into the callee body only when it resolves: a `func.id` bare name → the **module map**; a stripped `self`/`cls` method name → the **enclosing class's method map ONLY** (never the module map, never a sibling class's map). (`_extract_call_names` already emits the attribute form as the string `self._check_js_function_boundary`; resolution must strip the `self`/`cls` receiver to the bare method name `_check_js_function_boundary` and look it up in the enclosing class — matching on the raw `self.`-prefixed string, the original packet's wording, never resolves, which is exactly what mis-flagged the four boundary tests.) **Duplicate-name fail-closed:** if the stripped/bare name does not resolve to exactly one `FunctionDef` within its proper scope, contribute NO helper signal and do not recurse — never follow an arbitrary same-named definition from another class or a later shadowing def.
   - **(1b) Proof-class preservation — second REQUEST_CHANGES fix.** A resolved helper must contribute its FULL proof-class signal set to `classify_method`, not only `has_assertion`. The recursion must also surface the helper's source_lock signals (`SOURCE_LOCK_CALLS` membership and `.read_text()` / `open(` in the helper body — the same signals `classify_method` already computes for the test body) and behavioral signals (`BEHAVIORAL_CALLS` / raise / subprocess). `classify_method` then folds helper-derived `has_source`, `has_behavioral`, and `has_assertion` into its existing decision ladder before choosing source_lock/behavioral/hybrid. Required consequence: a test whose only assertions live in a source-reading helper (`_check_js_function_boundary` does `filepath.read_text()` then asserts on JSDoc) classifies **source_lock** — never behavioral, never theater_risk. Propagating helper assertions without helper source signals (silently downgrading source_lock → behavioral) is a defect, not an acceptable outcome.
   - Bounds: same-module only (no cross-file), recursion depth ≤ 2, cycle-guarded (track visited function names), callee normalization limited to bare-name and `self`/`cls` method calls (no arbitrary attribute-receiver resolution). Resolution is **scope-correct**: bare-name calls resolve against the module map, `self`/`cls` calls against the enclosing class's method map only, and any name that does not resolve uniquely within its proper scope is **fail-closed** (no recursion, no helper signal) — the classifier never follows an arbitrary later same-named helper. The resolution scope tracks the function being entered (a method recurses within its own class; a module-level helper recurses against the module map).

2. No-exception-is-pass validators (detector 2). `_has_raise_or_subprocess` recognizes `subprocess.run` / `_run_js_expr` / `ast.Raise` but not calls to validators that raise on failure (the call itself is the assertion). Fix: add a small explicit module-level set of recognized raises-on-failure validator call-names — seed it with `validate_bundle`, `validateBundle`, `_validate_template` (the names in the founder-allowlist entries' defer_reasons, per the TASKS.md tracker note) — and treat a test-body `ast.Call` to one of those names as a meaningful check. Route it through the same recursion (and the same (1a) callee normalization) as detector 1 so helper-wrapped validator calls also count.

3. Regression tests (added to the existing test file). (a) a test whose only assertion lives in a same-module **bare-name** helper that does no source read → classifies behavioral, not theater_risk; (b) a test whose only check is a `self._helper(...)` method whose helper does `filepath.read_text()` then asserts → classifies **source_lock**, not behavioral and not theater_risk (covers the (1a) `ast.Attribute`/self normalization and the (1b) source-lock preservation together; mirrors the real `_check_js_function_boundary` case); (c) a test whose only check is a `validate_bundle()` call → classifies behavioral; (d) a genuinely vacuous test (`assert True`) → still classifies theater_risk; (e) **duplicate-name scoping** — two test methods in two different classes that each call a SAME-NAMED `self._helper(...)`, where one class's helper does `read_text()` + assert and the other's does a plain non-source assert → the source-reading class's test classifies **source_lock** and the other classifies **behavioral**, proving `self`/`cls` resolution is class-scoped and a flat map's last-definition collapse cannot misroute the proof class (the live `_js_eval`-across-five-classes hazard).

## Constraints

Not in scope (HARD SCOPE — do not deviate or broaden):
- ONLY these two detectors. Do not add any other classification heuristics.
- Keep `THEATER_PATTERNS` (assert True / assert 1 vacuous detection) UNCHANGED.
- The source/behavioral/hybrid **decision ladder** in `classify_method` (has_source → source_lock, has_behavioral → behavioral, both → hybrid) stays UNCHANGED. Helper recursion ONLY augments the `has_source` / `has_behavioral` / `has_assertion` *inputs* with same-module helper signals — and it MUST propagate helper source_lock signals so a source-reading helper keeps its test classified source_lock. Silently downgrading source_lock → behavioral is forbidden.
- Do NOT change `scan_directory` or the classifier JSON schema — `check_theater_risk_ratchet.validate_classifier_results` must still pass.
- Callee normalization is limited to bare `ast.Name` calls and `self`/`cls` `ast.Attribute` method calls — no arbitrary attribute-receiver resolution, no cross-file resolution; recursion depth ≤ 2; cycle-guarded. Resolution MUST be scope-correct (bare names → module map; `self`/`cls` → enclosing class's method map only) and MUST fail closed on any name that does not resolve uniquely within its proper scope. A single flat global `{bare_name: FunctionDef}` map is forbidden — same-file classes reuse helper names (`_js_eval`, `_run_js`, `_run_js_builder`) and a flat map silently misroutes resolution to the last definition.
- Do NOT prune `theater_allowlist.json`. Pruning the now-unflagged entries is a separate downstream `--update-allowlist` step once this lands.
- Do NOT create a new test file (test-count growth-cap).
- No runtime-dir changes: do not touch `mu/host/...`, `rcx_pi/selfhost/...`, or any runtime substrate. This is L4_ENABLER tooling.
- Cite code by function name only; no file:line in the packet.

## Stop conditions

- STOP at the Phase A boundary: this packet is design only. Do not implement until Phase-A-Lock is LOCKED and Phase B is invoked.
- STOP and escalate to founder/bridge if either detector cannot be implemented without changing `THEATER_PATTERNS`, the classifier JSON schema, the source/behavioral/hybrid decision ladder, or `scan_directory` — that is a stop condition, not a license to broaden.
- STOP if helper recursion cannot count helper assertions WITHOUT silently downgrading a source-reading test from source_lock to behavioral — preserving the proof class is mandatory; ship neither the downgrade nor a partial fix, escalate instead.
- STOP if satisfying the detectors would require cross-file resolution, recursion deeper than 2, or callee normalization beyond bare-name + `self`/`cls` methods — the bounds are firm.
- STOP if the duplicate same-file helper-name case (e.g. the five `_js_eval` methods across five classes of `test_terminal_classification_parity_gate.py`) cannot be resolved by class/lexical scoping plus fail-closed lookup — a flat global map that follows an arbitrary later same-named helper is a defect, not an acceptable shortcut; escalate rather than ship it.
- STOP if the validation gate cannot pass without pruning `theater_allowlist.json` or creating a new test file.
- STOP after the classifier + tests land. Do NOT continue into the downstream `--update-allowlist` allowlist-pruning step (separate wave).
- If `validate_classifier_results` (schema) or `check_theater_risk_ratchet.py` regresses, STOP and fix before proceeding — never bypass the gate.

## Acceptance criteria

- `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/ -k "gate_behavioral or theater"` passes, including the five new regression tests (the evidence_command from the TASKS.md tracker note).
- `python3 tools/checks/check_theater_risk_ratchet.py` exits 0 — the classifier JSON schema still validates via `validate_classifier_results`.
- Real-world reclassification (the bridge-cited case): the four `TestJSOuterLoopBoundary` tests — `test_js_run_boundary`, `test_js_run_structural_boundary`, `test_js_run_algorithm_with_bridge_boundary`, `test_js_run_engine_pipeline_recursive_boundary` in `mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py`, all currently `theater_risk` (confirmed via `check_gate_behavioral_pairs.py --json`) — reclassify to **source_lock** because their helper `_check_js_function_boundary` reads JS source and asserts on JSDoc. They MUST NOT become behavioral and MUST NOT remain theater_risk.
- Proof-class behavior confirmed: a source-reading `self`/`cls` helper keeps its test source_lock; a no-source bare-name helper assertion → behavioral; a `validate_bundle()`-only test → behavioral; a vacuous `assert True` test → theater_risk.
- Duplicate same-file helper names resolve scope-correctly: the five `_js_eval` `self`-method helpers across the five classes of `test_terminal_classification_parity_gate.py` (and the duplicated `_run_js_builder` / `_run_js` helpers) each resolve within their own class — no test's proof class is determined by a same-named helper from a different class, and any unresolved/ambiguous name is fail-closed (no helper signal). Regression test (e) passes.
- Diff confined to the two detectors + the scope-keyed resolution maps (a module-level `{name: FunctionDef}` map plus a per-class method map) + the recursion threading + the new test cases. The source/behavioral/hybrid decision ladder, `THEATER_PATTERNS`, `scan_directory`, and the classifier JSON schema are unchanged; helper recursion only augments the classifier's `has_source` / `has_behavioral` / `has_assertion` inputs.
- No new test file created; `theater_allowlist.json` unchanged.
- Indicator artifact collectable: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id theater-classifier-broaden-2026-06-02 --output reports/l4_wave_indicators/theater-classifier-broaden-2026-06-02.json`.

## Grounding / Authorization

- Task `[NEXT-CODEX-POST-REDTEAM]` is authorized by the `TASKS.md` tracker note (2026-06-02, theater-classifier-broaden-2026-06-02): "broaden check_gate_behavioral_pairs theater classifier: follow same-module helper-fn assertions + recognize raises-on-failure validators (validate_bundle/validateBundle/_validate_template); classifier+tests only, no allowlist pruning."
- Governing packet: this file, `reports/control_plane/theater_classifier_broaden_2026-06-02.md` (the `Packet:` reference in that same TASKS.md tracker note).
- L4 classification (from the TASKS.md tracker note): Class L4_ENABLER; target_gate_id G8; evidence_command `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/ -k "gate_behavioral or theater"`; primary_blocker_class INTEGRATION; primary_invariant_id INV_STRUCTURAL_FORWARD_MOTION; indicator_artifact_ref reports/l4_wave_indicators/theater-classifier-broaden-2026-06-02.json; bootstrap_endgame_policy SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP; boot0_track_id V1; boot0_progress_state HOLD.
- Same-wave override (wave-bound, present verbatim in the TASKS.md tracker note for this wave): `FOUNDER_OVERRIDE:theater-classifier-broaden-2026-06-02`. Commit automation derives the same-wave override mechanically from this token.
- Authorization: standing pipeline-bug-fix authorization per memory `feedback_autonomous_executor_fix.md` — the same standing authorization the sibling 2026-06-02 L4_ENABLER waves (`stranded-pr-recovery-2026-06-02`, `bridge-config-model-sync-2026-06-02`) carry in TASKS.md for commit-gate + pre-push adjacency-cap clearance.
- Upstream context: this is the queued classifier fix that the `theater-allowlist-refresh-2026-06-02` tracker note (TASKS.md) names as the remedy for the dominant share of the founder-allowlisted heuristic_false_positive entries — per that note, the helper-assertion and no-exception-is-pass blindspots account for ~65 of the 75 renewed entries that re-expire 2026-07-02. Landing this broadening lets a later `--update-allowlist` step prune the now-unflagged entries before that re-expiry.

## Request from Post-Merge Supervisor

Broaden the theater-risk classifier `tools/checks/check_gate_behavioral_pairs.py` (the CLASSIFIER_SCRIPT that check_theater_risk_ratchet.py runs) to stop mis-flagging two specific REAL-assertion patterns as theater_risk. READ these existing functions first: `_has_meaningful_assertion(node)`, `_has_raise_or_subprocess(node)`, `classify_method(func_node)`, `scan_file(filepath)`. TWO PRECISE, BOUNDED FIXES (do not deviate, do not broaden beyond these): (1) HELPER-FUNCTION ASSERTIONS: `_has_meaningful_assertion` currently scans only the function's OWN body (ast.walk over the test node), so assertions made inside SAME-MODULE helper functions the test calls (e.g. _source_step, _run_js_vm, _check_js_function_boundary, _js_eval) are missed -> false theater_risk. FIX: in scan_file, collect the module's top-level + nested FunctionDefs into a {name: FunctionDef} map; thread it into classify_method / _has_meaningful_assertion; when scanning a test function, for each ast.Call to a name in that SAME-MODULE map, recursively check the callee's body for meaningful assertions / raise-or-subprocess. Bound it: same-module only (no cross-file), recursion depth <=2, cycle-guarded (track visited function names). (2) NO-EXCEPTION-IS-PASS VALIDATORS: `_has_raise_or_subprocess` recognizes subprocess.run / _run_js_expr / ast.Raise but NOT calls to validators that RAISE on failure (the call itself is the assertion). FIX: add a small EXPLICIT module-level set of recognized raises-on-failure validator call-names -- seed it with validate_bundle, validateBundle, _validate_template (the names in the 75 allowlist entries' defer_reasons) -- and treat a test-body ast.Call to one of those names as a meaningful check (route it through the same recursion in fix (1) so helper-wrapped validator calls also count). HARD SCOPE: ONLY these two detectors. Keep THEATER_PATTERNS (assert True / assert 1) vacuous-detection UNCHANGED. Do NOT change the source_lock/behavioral classification, scan_directory, or the classifier JSON schema (check_theater_risk_ratchet.validate_classifier_results must still pass). Same-module helper resolution ONLY. This wave fixes the CLASSIFIER + adds tests ONLY -- do NOT prune theater_allowlist.json (that is a separate downstream --update-allowlist step once this lands).

Routed next-candidate:
theater-classifier-broaden-2026-06-02

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `theater-classifier-broaden-2026-06-02`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/theater-classifier-broaden-2026-06-02_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `theater-classifier-broaden-2026-06-02`
- Active packet: `reports/control_plane/theater_classifier_broaden_2026-06-02.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `24cad4b7a6a0787001c0b208716fe44718954bfc49ef5be4b82d2c3705070ed5`
- Indicator artifact: `reports/l4_wave_indicators/theater-classifier-broaden-2026-06-02.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_check_gate_behavioral_pairs.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/theater_classifier_broaden_2026-06-02.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/theater-classifier-broaden-2026-06-02.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_check_gate_behavioral_pairs.py`
  - `mu/tools/checks/check_gate_behavioral_pairs.py`
  - `reports/control_plane/theater_classifier_broaden_2026-06-02.md`
  - `reports/deferred/non_blocking/theater-classifier-broaden-2026-06-02_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/theater-classifier-broaden-2026-06-02.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
