# Check Test Theater Ast 2026-06-03

Date: 2026-06-03
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: check-test-theater-ast-2026-06-03
Phase-A-Lock: LOCKED
Purpose: AST-ify the test-theater check so it stops false-positiving on vacuous-assertion patterns that appear INSIDE test FIXTURE STRINGS, AND wire the new linter FAIL-CLOSED so a linter execution failure cannot silently pass the gate. READ FIRST: tools/checks/check_test_theater.sh (its six vacuous-assertion `check_pattern` greps for `assert True`, `assert 1`, `assertTrue(True)`, `assertEqual(True,True)`/`(1,1)`/`(0,0)`, plus the PRESERVED non-vacuous checks: self-comparison `assert x == x`, single-line empty bodies, an inline multiline-empty-body AST block, skip-without-reason decorators, commented-out assertions, TODO/FIXME placeholders; it runs under `set -e` and accumulates into ERRORS with a SINGLE end-of-script exit), and the EXISTING AST linter tools/checks/linters/check_private_attr_access.py (mirror its NodeVisitor/per-file try-except/CLI structure). BUG #1 (original): the six vacuous greps are TEXT-based, so a vacuous assertion inside a string-literal fixture (e.g. `f.write_text(textwrap.dedent('''...assert True'''))` verifying a classifier) is a FALSE positive (observed 2026-06-03 PR #1065, worked around with THEATER_OK). BUG #2 (FAIL-OPEN, the blocker that must be fixed this time): a naive rewire that runs `out=$(python3 linter 2>/dev/null || true)` and treats only NON-EMPTY stdout as a finding MASKS linter execution failure -- if the linter has a syntax/import/runtime failure it prints nothing to stdout, the nonzero exit is swallowed by `|| true`, so the scan is silently skipped and the gate exits 0 (a fail-open control-surface defect). The wrapper MUST capture the linter exit status with a `set -e`-SAFE GUARDED capture -- `if out=$(...); then rc=0; else rc=$?; fi` (equivalently `out=$(...) && rc=0 || rc=$?`) -- and NEVER a bare `out=$(...); rc=$?`, which under `set -e` fail-fasts on the failing command substitution and exits the script before `rc=$?` (or the branch) ever runs (see Red-team resolution below for the verified reproduction). BUG #3 (SCAN-NOTHING FAIL-OPEN, bridge round 2 -- the new blocker; this SUPERSEDES the "mirror ... CLI structure" shorthand above): mirror ONLY check_private_attr_access.py's NodeVisitor + per-file try-except STRUCTURE, NOT its CLI/path-discovery. That exemplar's `main` sets `root=Path(argv[1])` and its `scan(root)` re-discovers hard-coded `SCAN_DIRS=("tests","mu/tests")` BELOW that root (silently `continue`-ing when a subdir is absent), so mirroring the CLI literally under the wrapper call `check_test_theater.py "$TESTS_DIR"` (TESTS_DIR=tests) would search `tests/tests`+`tests/mu/tests`, match nothing, and exit 0 CLEAN -- the replacement linter would scan nothing and silently pass, the exact fail-open this wave exists to kill. FIX: the new linter's argv[1] is the directory to scan DIRECTLY (walk it recursively for `*.py`), parity with this gate's own in-line `os.walk(tests_dir)` multiline-empty block and with how `check_pattern` greps `$TESTS_DIR` directly -- NOT the exemplar's argv-as-root + SCAN_DIRS re-discovery; and a target resolving to ZERO `*.py` files is an EXECUTION ERROR (exit >=2), never a clean exit 0, so scanning nothing FAILS the gate (belt-and-suspenders fail-closure).

## Scope

Files/directories IN scope (exactly four; one new file, three edits):

- `tools/checks/linters/check_test_theater.py` -- NEW AST linter (mirror `check_private_attr_access.py`'s NodeVisitor + per-file try-except STRUCTURE ONLY -- NOT its CLI/path-discovery: argv[1] is the directory to scan DIRECTLY, NOT a root under which hard-coded `tests/`+`mu/tests/` are re-discovered, else `check_test_theater.py tests` scans `tests/tests`, finds nothing, and fail-opens -- see BUG #3 / Red-team round 2). Flags a vacuous assertion ONLY as a REAL statement: `ast.Assert` whose test is a constant-truthy literal (`assert True` / `assert 1`) and `ast.Call` to `assertTrue(True)` / `assertEqual(True, True)` / `assertEqual(1, 1)` / `assertEqual(0, 0)`. MUST NOT flag those tokens inside a string literal (`ast.Constant` str) or docstring -- fixture strings are ignored, which is the whole point. Honors a trailing `# THEATER_OK: reason`. EXIT-CODE CONTRACT (detection is BY EXIT CODE, not stdout-presence): `0` = scanned cleanly / no vacuous findings; `1` = scanned, real vacuous finding(s) found (print offending `file:line` to stdout); `>=2` = EXECUTION ERROR (could not scan) -- which INCLUDES a target path that resolves to ZERO `*.py` files, so scanning nothing FAILS closed and never exits 0. Because detection is by exit code, the linter MAY print a short header.
- `tools/checks/check_test_theater.sh` -- EDIT: surgically replace ONLY the six vacuous-assertion `check_pattern` calls with ONE guarded, accumulating, FAIL-CLOSED invocation of the new linter (see Work items for the exact `set -e`-safe pattern).
- `mu/tests/docs/test_growth_caps.py` -- EDIT: pre-bump `CAP_TOOL_SCRIPTS` +1 for the new linter.
- One EXISTING `mu/tests/tools/` test file -- EDIT: add the regression test (no new test file; growth-cap bound).

L4 class: L4_ENABLER (control-surface check hardening; touches NO runtime/substrate dir). Callers (`green_gate.sh` / `audit_fast.sh` / `audit_all.sh`) and the JS variant (`check_test_theater_js.sh`) are untouched and fixed transitively. Cite code by function/file name only; no file:line.

## Work items

Concrete bounded tasks (current phase, [NEXT-CODEX-POST-REDTEAM], per TASKS.md tracker note for wave check-test-theater-ast-2026-06-03):

1. CREATE `tools/checks/linters/check_test_theater.py`. AST scanner mirroring `check_private_attr_access.py`'s NodeVisitor + per-file try-except STRUCTURE ONLY -- do NOT mirror its CLI/path-discovery. CLI CONTRACT (this is the bridge-round-2 fix): `argv[1]` is the directory to scan DIRECTLY -- walk it recursively for `*.py` test files (parity with this gate's own in-line `os.walk(tests_dir)` multiline-empty block and with how `check_pattern` greps `$TESTS_DIR` directly). Do NOT copy the exemplar's `scan(root)` semantics, which treat argv[1] as a repo ROOT and re-discover hard-coded `SCAN_DIRS=("tests","mu/tests")` below it -- under the wrapper call `check_test_theater.py "$TESTS_DIR"` with TESTS_DIR=tests that would search `tests/tests`+`tests/mu/tests`, scan nothing, and exit 0 clean (a SCAN-NOTHING FAIL-OPEN). Visit `ast.Assert` (flag constant-truthy literal test) and `ast.Call` (flag `assertTrue(True)` / `assertEqual` tautologies). Do NOT descend into / flag string literals or docstrings (`ast.Constant` str) -- that is what fixes the PR #1065 fixture-string false positive. Honor trailing `# THEATER_OK: reason`. Implement the exit-code contract exactly: `0` clean, `1` real findings (offending `file:line` to stdout), `>=2` execution error. A target path that resolves to ZERO `*.py` files is an EXECUTION ERROR (exit `>=2`), never a clean exit 0 -- so scanning nothing FAILS the gate (fail-closed defense-in-depth against the round-2 finding). Per-file try-except so one unparseable target is an EXECUTION ERROR (exit `>=2`), not a silent skip.

2. EDIT `tools/checks/check_test_theater.sh`. Replace ONLY the six vacuous-assertion `check_pattern` calls with a single guarded, accumulating, FAIL-CLOSED block. The capture MUST be `set -e`-safe (verified -- see Red-team resolution):

   ```bash
   # Replaces ONLY the six vacuous-assertion check_pattern calls.
   # CLI CONTRACT: the linter scans "$TESTS_DIR" DIRECTLY (argv[1] = the dir to walk
   # recursively); it must NOT treat argv[1] as a root that re-discovers tests/+
   # mu/tests/ below it (that scans tests/tests, finds nothing, and fail-opens). See item 1.
   # set -e SAFE: the guarded `if` (equivalently `... && rc=0 || rc=$?`) stops a
   # nonzero linter exit from fail-fasting the script before the branch runs.
   # A bare `out=$(...); rc=$?` is FORBIDDEN: under set -e the failing command
   # substitution exits the script and rc=$? / the branch never run.
   if out=$(python3 "$(dirname "$0")/linters/check_test_theater.py" "$TESTS_DIR" 2>&1); then
     rc=0
   else
     rc=$?
   fi
   if [ "$rc" -eq 0 ]; then
     :                                  # rc==0: scanned clean -> continue
   elif [ "$rc" -eq 1 ]; then
     printf '%s\n' "$out"               # rc==1: real vacuous finding(s)
     ERRORS=$((ERRORS + 1))             # accumulate, continue
   else
     printf '%s\n' "$out"               # rc>=2: EXECUTION FAILURE
     ERRORS=$((ERRORS + 1))             # FAIL CLOSED -- never treat as clean, continue
   fi
   ```

   HARD invariant: ANY nonzero linter exit increments ERRORS (never swallowed by `|| true` + stdout-presence), so a linter crash FAILS the gate instead of silently passing. PRESERVE the gate's `set -e` accumulate-and-continue contract -- NO `|| exit 1` fail-fast, NO bare command; the single end-of-script ERRORS check stays the only exit point (mirror the existing in-gate multiline-empty-body AST block's accumulate-then-continue style, NOT `green_gate.sh`/`audit_fast.sh`'s fail-fast `|| exit 1`). PRESERVE byte-for-byte every OTHER existing check (self-comparison, single-line + multiline empty bodies, skip-without-reason, commented-out assertions, TODO/FIXME) -- the new linter scopes to vacuous assertions ONLY and does NOT subsume them.

3. EDIT `mu/tests/docs/test_growth_caps.py`. Pre-bump `CAP_TOOL_SCRIPTS` +1 with inline comment `+1 for check_test_theater.py (FOUNDER_OVERRIDE:check-test-theater-ast-2026-06-03)`.

4. EDIT one EXISTING `mu/tests/tools/` test file (no new test file). Regression test covering SIX behaviors: (a) `assert True` inside a `textwrap.dedent` fixture string -> CLEAN (not theater); (b) a real top-level `assert True` -> FLAGGED; (c) a `# THEATER_OK` line -> skipped; (d) FAIL-CLOSED: when the linter invocation FAILS to execute (simulate exit `>=2`), the gate FAILS (ERRORS>0 / nonzero) and does NOT exit 0; (e) SCAN-COVERAGE: the linter invoked exactly as the wrapper invokes it (argv[1] = the scan dir) FLAGS a real `assert True` that lives in a file UNDER that dir -- proving it scans the passed directory directly and does NOT scan-nothing by re-discovering a wrong root; (f) ZERO-FILES FAIL-CLOSED: pointed at a directory containing no `*.py` files, the linter exits `>=2` (not 0), so scanning nothing fails the gate.

## Constraints

NOT in scope (do not touch; STOP and escalate if any appears necessary):

- Callers `green_gate.sh` / `audit_fast.sh` / `audit_all.sh` -- they only CALL `check_test_theater.sh` (no inline vacuous grep); fixed transitively.
- The JS variant `check_test_theater_js.sh`, any other check, or any runtime/substrate dir (`rcx_pi/selfhost/`, `mu/host/`). L4_ENABLER MUST NOT touch runtime dirs.
- No new file other than the single linter `check_test_theater.py`. No new test file (growth cap) -- the regression goes into an EXISTING `mu/tests/tools/` file.
- Do NOT drop or subsume the non-vacuous checks; do NOT convert the gate to fail-fast (`|| exit 1`); do NOT introduce a bare `out=$(...); rc=$?` capture.
- Do NOT mirror `check_private_attr_access.py`'s CLI/path-discovery (argv-as-root + hard-coded `SCAN_DIRS` re-discovery). The new linter's argv[1] is the directory to scan DIRECTLY; copying the exemplar's `scan(root)` makes `check_test_theater.py tests` search `tests/tests`+`tests/mu/tests`, scan nothing, and fail-open. Mirror ONLY its NodeVisitor + per-file try-except structure.
- Cite code by function/file name only; no file:line.

## Stop conditions

- DONE when the four in-scope files are changed and both Acceptance gates pass on the clean tree. Do not expand beyond the four files.
- HALT-AND-ESCALATE if a correct fix appears to require editing a caller, the JS variant, any other check, or any runtime/substrate dir -- that is a scope/contract breach, not a license to widen.
- HALT if the change would require a second new file or a new test file (growth-cap violation) -- the regression MUST land in an existing `mu/tests/tools/` file.
- HALT if `bash tools/checks/check_test_theater.sh tests` cannot reach exit 0 on the clean tree without weakening a preserved non-vacuous check.
- HALT if the new linter cannot be shown to scan `$TESTS_DIR` directly (e.g. `check_test_theater.py tests` scans `tests/tests` or resolves zero `*.py` files) -- that is the scan-nothing fail-open this round must close; correct the CLI contract before proceeding, never ship a linter that can pass by scanning nothing.
- Phase A stops at this packet. Do NOT begin implementation in the planning turn; implementation runs under Phase B per the executor pipeline.

## Acceptance criteria

- `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/ -k "test_theater or check_test_theater"` passes (TASKS.md evidence_command for this wave).
- `bash tools/checks/check_test_theater.sh tests` exits 0 on the clean tree.
- The regression test proves all SIX behaviors: fixture-string `assert True` -> clean; real top-level `assert True` -> flagged; `# THEATER_OK` -> skipped; linter execution failure (exit `>=2`) -> gate FAILS (ERRORS>0, nonzero) and does NOT exit 0; SCAN-COVERAGE -> the linter invoked exactly as the wrapper invokes it (argv[1] = the scan dir) flags a real `assert True` living UNDER that dir (proves it scans the passed directory directly, not a re-discovered root); ZERO-FILES -> a target with no `*.py` files exits `>=2` (scan-nothing FAILS closed, never exit 0).
- The new linter scans `$TESTS_DIR` DIRECTLY (argv[1] = directory walked recursively), mirroring ONLY the exemplar's NodeVisitor + per-file try-except structure -- NOT `check_private_attr_access.py`'s argv-as-root + `SCAN_DIRS` re-discovery; `check_test_theater.py tests` from the repo root scans `tests/` itself (not `tests/tests`), so the replacement cannot scan nothing and silently pass.
- The wrapper uses the `set -e`-safe guarded capture (`if out=$(...); then rc=0; else rc=$?; fi`); a bare `out=$(...); rc=$?` is absent. ANY nonzero linter exit increments ERRORS.
- Non-vacuous checks preserved byte-for-byte; the single end-of-script ERRORS exit remains the only exit point; callers and the JS variant unchanged.
- `CAP_TOOL_SCRIPTS` bumped +1 with the inline FOUNDER_OVERRIDE comment; exactly one new file (the linter).

## Grounding / Authorization

- Authorizing record: TASKS.md tracker sync note (2026-06-03, check-test-theater-ast-2026-06-03) for [NEXT-CODEX-POST-REDTEAM]. Class: L4_ENABLER. target_gate_id: G8. Packet: `reports/control_plane/check_test_theater_ast_2026-06-03.md` (this file, the governing packet).
- FOUNDER_OVERRIDE:check-test-theater-ast-2026-06-03
- Authorization: standing pipeline-bug-fix authorization (per memory feedback_autonomous_executor_fix.md; control-surface check/gate hardening, no runtime dirs), wave-bound so commit automation derives the same-wave override mechanically for commit-gate + pre-push adjacency-cap clearance.
- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/ -k "test_theater or check_test_theater"`
- evidence_delta: new `check_test_theater.py` (AST, exit-code contract 0/1/>=2) replaces the six grep vacuous-assertion checks; `check_test_theater.sh` rewired FAIL-CLOSED (captures rc, ERRORS++ on any nonzero, no `|| true` swallow); non-vacuous checks + `set -e` accumulate-and-continue preserved; CAP_TOOL_SCRIPTS +1; regression (incl. exec-failure) in an existing test file.
- primary_blocker_class: INTEGRATION. primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION.
- indicator_artifact_ref: `reports/l4_wave_indicators/check-test-theater-ast-2026-06-03.json`
- indicator_collection_command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id check-test-theater-ast-2026-06-03 --output reports/l4_wave_indicators/check-test-theater-ast-2026-06-03.json`
- bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. boot0_track_id: V1. boot0_progress_state: HOLD.

## Red-team resolution (bridge round 1, REQUEST_CHANGES)

- [high] DEFECT -- rc capture fails under `set -e` before the branch runs: FIXED. The prescribed pattern is now the `set -e`-safe guarded capture `if out=$(...); then rc=0; else rc=$?; fi` (Work item 2); the bare `out=$(...); rc=$?` is explicitly forbidden. Verified: under `set -e`, the bare form yields only `outer_rc=1` (branch never reached), while the guarded form reaches the branch and accumulates ERRORS for rc=0/1/>=2 -- preserving the accumulate-and-continue + single end-of-script exit contract.
- [high] DEFECT -- required stop conditions absent: FIXED. Added explicit `## Stop conditions` (plus `## Work items`, `## Constraints`, `## Acceptance criteria`).
- [high] POLICY_BOUND -- grounding/authorization not explicit: FIXED. Added `## Grounding / Authorization` referencing the TASKS.md tracker note, the wave-bound `FOUNDER_OVERRIDE:check-test-theater-ast-2026-06-03`, and an explicit `Authorization: standing pipeline-bug-fix authorization` line so commit automation can derive the same-wave override.

## Red-team resolution (bridge round 2, REQUEST_CHANGES)

- [high] DEFECT -- linter CLI contract can degrade into a scan-nothing pass if the referenced exemplar is mirrored literally: FIXED. Verified against code truth: `check_test_theater.sh` scans `$TESTS_DIR` DIRECTLY (`check_pattern` greps `"$TESTS_DIR"`; the in-line multiline-empty block does `os.walk(tests_dir)` on `$TESTS_DIR`), whereas `check_private_attr_access.py`'s `main` sets `root=Path(argv[1])` and `scan(root)` re-discovers hard-coded `SCAN_DIRS=("tests","mu/tests")` below that root (silently `continue`-ing on absent subdirs). Mirroring that CLI literally under `check_test_theater.py "$TESTS_DIR"` (TESTS_DIR=tests) would search `tests/tests`+`tests/mu/tests`, find nothing, and exit 0 clean -- a SCAN-NOTHING FAIL-OPEN that would defeat the entire wave (a hardening change that silently scans nothing). The packet now specifies the new linter mirrors ONLY the exemplar's NodeVisitor + per-file try-except STRUCTURE, NOT its CLI/path-discovery: argv[1] is the directory to scan DIRECTLY (Scope, Work item 1, BUG #3, Constraints), with belt-and-suspenders fail-closure -- a target resolving to ZERO `*.py` files is an EXECUTION ERROR (exit `>=2`), never exit 0. Acceptance + Work item 4 add a SCAN-COVERAGE proof (the linter invoked as the wrapper invokes it flags a real `assert True` under the scanned tree) and a ZERO-FILES fail-closed proof, behaviors (e)+(f); a Stop condition HALTs if the linter cannot be shown to scan `$TESTS_DIR` directly.

## Request from Post-Merge Supervisor

AST-ify the test-theater check so it stops false-positiving on vacuous-assertion patterns that appear INSIDE test FIXTURE STRINGS, AND wire the new linter FAIL-CLOSED so a linter execution failure cannot silently pass the gate. READ FIRST: tools/checks/check_test_theater.sh (its six vacuous-assertion `check_pattern` greps for `assert True`, `assert 1`, `assertTrue(True)`, `assertEqual(True,True)`/`(1,1)`/`(0,0)`, plus the PRESERVED non-vacuous checks: self-comparison `assert x == x`, single-line empty bodies, an inline multiline-empty-body AST block, skip-without-reason decorators, commented-out assertions, TODO/FIXME placeholders; it runs under `set -e` and accumulates into ERRORS with a SINGLE end-of-script exit), and the EXISTING AST linter tools/checks/linters/check_private_attr_access.py (mirror its NodeVisitor/per-file try-except/CLI structure). BUG #1 (original): the six vacuous greps are TEXT-based, so a vacuous assertion inside a string-literal fixture (e.g. `f.write_text(textwrap.dedent('''...assert True'''))` verifying a classifier) is a FALSE positive (observed 2026-06-03 PR #1065, worked around with THEATER_OK). BUG #2 (FAIL-OPEN, the blocker that must be fixed this time): a naive rewire that runs `out=$(python3 linter 2>/dev/null || true)` and treats only NON-EMPTY stdout as a finding MASKS linter execution failure -- if the linter has a syntax/import/runtime failure it prints nothing to stdout, the nonzero exit is swallowed by `|| true`, so the scan is silently skipped and the gate exits 0 (a fail-open control-surface defect). PRECISE FIX (exactly four in-scope files, no new files beyond the one linter): (1) CREATE tools/checks/linters/check_test_theater.py -- an AST scanner (mirror check_private_attr_access.py) that flags a vacuous assertion ONLY as a REAL statement: ast.Assert whose test is a constant-truthy literal (`assert True`/`assert 1`) and ast.Call to assertTrue(True)/assertEqual(True,True)/assertEqual(1,1)/assertEqual(0,0); it MUST NOT flag those tokens inside a string literal (ast.Constant str) or docstring (fixture strings are ignored -- the whole point); honors a trailing `# THEATER_OK: reason`. EXIT-CODE CONTRACT (this is the fail-closed fix -- DETECTION IS BY EXIT CODE, NOT stdout-presence): exit 0 = scanned cleanly, no vacuous findings; exit 1 = scanned, real vacuous finding(s) found (print the offending `file:line` lines to stdout); exit >=2 = EXECUTION ERROR (could not scan -- e.g. an unparseable target it chooses to treat as error, or an internal failure). Because detection is by exit code, the linter MAY print a short header; the old 'print nothing to stdout when clean' constraint NO LONGER applies. (2) EDIT tools/checks/check_test_theater.sh -- SURGICALLY replace ONLY the six vacuous-assertion `check_pattern` calls with a SINGLE GUARDED, ACCUMULATING, FAIL-CLOSED invocation that CAPTURES THE LINTER EXIT STATUS via a `set -e`-safe guarded capture (`if out=$(python3 "$(dirname "$0")/linters/check_test_theater.py" "$TESTS_DIR" 2>&1); then rc=0; else rc=$?; fi` -- NOT a bare `out=$(...); rc=$?`, which fail-fasts under `set -e` before the branch runs) then branch on `rc` -- rc==0 clean (continue); rc==1 real findings (print them, ERRORS=$((ERRORS+1)), continue); rc>=2 EXECUTION FAILURE (print the captured output, ERRORS=$((ERRORS+1)) -- FAIL CLOSED, do NOT treat as clean, continue). The HARD invariant: ANY nonzero linter exit must increment ERRORS (never be swallowed by `|| true` + stdout-presence), so a linter crash FAILS the gate instead of silently passing. PRESERVE the gate's `set -e` accumulate-and-continue contract -- NO `|| exit 1` fail-fast and NO bare command (either would exit on the first finding before the preserved non-vacuous checks run); the single end-of-script ERRORS check stays the only exit point (mirror the existing in-gate multiline-empty-body AST block's accumulate-then-continue style, NOT green_gate.sh/audit_fast.sh's fail-fast `|| exit 1`). PRESERVE byte-for-byte every OTHER existing check (self-comparison, single-line + multiline empty bodies, skip-without-reason, commented-out assertions, TODO/FIXME) -- the new linter scopes to vacuous assertions ONLY and does NOT subsume them; do NOT drop the whole grep scan. (3) EDIT mu/tests/docs/test_growth_caps.py -- PRE-BUMP CAP_TOOL_SCRIPTS +1 for the new linter, inline comment `+1 for check_test_theater.py (FOUNDER_OVERRIDE:check-test-theater-ast-2026-06-03)`. (4) EDIT one EXISTING mu/tests/tools/ test file (NO new test file -- growth cap) -- regression test covering FOUR behaviors: (a) `assert True` inside a textwrap.dedent fixture string -> CLEAN (not theater); (b) a real top-level `assert True` -> FLAGGED; (c) a `# THEATER_OK` line -> skipped; and (d) FAIL-CLOSED: when the linter invocation FAILS to execute (simulate an execution failure -- e.g. invoke the gate/wrapper with the linter raising or otherwise exiting >=2), the gate FAILS (ERRORS>0 / nonzero) and does NOT exit 0. HARD SCOPE: ONLY check_test_theater.sh + the new check_test_theater.py + test_growth_caps.py + one existing mu/tests/tools/ test file. Do NOT touch the callers (green_gate.sh/audit_fast.sh/audit_all.sh -- they only CALL check_test_theater.sh, VERIFIED no inline grep), the JS variant check_test_theater_js.sh, or any other check, or any runtime/substrate dir. Cite code by function/file name only; no file:line.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `check-test-theater-ast-2026-06-03`
- Active packet: `reports/control_plane/check_test_theater_ast_2026-06-03.md`
- Indicator artifact: `reports/l4_wave_indicators/check-test-theater-ast-2026-06-03.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/tools/test_check_test_theater_detection.py`
  - `mu/tools/checks/check_test_theater.sh`
  - `mu/tools/checks/linters/check_test_theater.py`
  - `reports/control_plane/check_test_theater_ast_2026-06-03.md`
  - `reports/l4_wave_indicators/check-test-theater-ast-2026-06-03.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `check-test-theater-ast-2026-06-03`
- Active packet: `reports/control_plane/check_test_theater_ast_2026-06-03.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `754a802bd69d13ec252dd8248fda025e055c91b96da7309d124fc352bd9b9f8e`
- Indicator artifact: `reports/l4_wave_indicators/check-test-theater-ast-2026-06-03.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/tools/test_check_test_theater_detection.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/check_test_theater_ast_2026-06-03.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/check-test-theater-ast-2026-06-03.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/tools/test_check_test_theater_detection.py`
  - `mu/tools/checks/check_test_theater.sh`
  - `mu/tools/checks/linters/check_test_theater.py`
  - `reports/control_plane/check_test_theater_ast_2026-06-03.md`
  - `reports/l4_wave_indicators/check-test-theater-ast-2026-06-03.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
