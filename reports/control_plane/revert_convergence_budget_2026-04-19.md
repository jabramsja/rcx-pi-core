Phase-A-Lock: UNLOCKED

# Revert 3-round convergence budget — 2026-04-19

Status: Phase A (UNLOCKED, plan draft v3 — rewrite addressing bridge
REQUEST_CHANGES 2026-04-19 findings: (1) stale deletion-zone references in
§1/§2, (2) A6 regression-test coverage inconsistent with W4's three-test
surface)

wave_id: revert-convergence-budget-2026-04-19

## 1. Scope

Single runtime file: `mu/tools/executors/phase_a_executor.py`.

The revert of the predecessor wave's 3-round convergence budget (predecessor
`bridge-convergence-budget-2026-04-18`, TASKS.md:149, PR #796) is **already
applied in the working tree**. Re-verified 2026-04-19 with the reviewer's
exact reproduce command from blocking finding #1:

- `rg -n "convergence_budget|blocking_rounds_in_pass|convergence budget|blocking REQUEST_CHANGES rounds in pass" mu/tools/executors/phase_a_executor.py`
  returns zero matches.

The abort branch TASKS.md:149 described inserting ("At round >= 3 with
blocking findings, returns status=error with clear message instead of
continuing to max_bridge_rounds ceiling") is therefore gone from the file.
The `_run_bridge_convergence` loop header at `phase_a_executor.py:1202`
remains `range(start_round, max_bridge_rounds + 1)`, restoring the original
15-round ceiling when REQUEST_CHANGES persists. File is 1626 lines.

No other file is changed by this wave.

## 2. Work items (bounded)

The three code-deletion work items from draft v2 (W1–W3, targeting
`convergence_budget = 3`, `blocking_rounds_in_pass = 0`, and the 3-round
abort branch) are **retracted**. Bridge REQUEST_CHANGES 2026-04-19 finding #1
proved via `rg` that the referenced identifiers and abort branch are already
absent in the current file state, so they are not pending work. Re-listing
them as "to do" would be dishonest against current code truth.

What remains as bounded work for this wave:

W1. Keep existing Phase A bridge-loop regression tests green; do not add
    new tests. The behavioral regression surface for this revert lives in
    `mu/tests/tools/test_executor_dispatch.py`:

    - `:1173` `test_request_changes_continues_loop` — with
      `max_bridge_rounds=5`, asserts Phase A continues past 2 REQUEST_CHANGES
      rounds into GO at round 3, expecting `status == "converged"` and
      `call_count == 3`.
    - `:1198` `test_non_go_exit_one_continues_loop` (parametrized via
      `@pytest.mark.parametrize("decision", ["REQUEST_CHANGES", "NO_GO"])`
      at `:1197`) — same loop-continuation contract when `bridge_supervisor`
      exits with code 1 for non-GO decisions.
    - `:6927` `test_all_request_changes_returns_max_rounds_not_success` —
      with `max_bridge_rounds=3`, all-REQUEST_CHANGES rounds must yield
      `status == "max_rounds_reached"` (not early-abort to `"error"`),
      `"error" in result`, and `call_count == 3`.

    These tests emit REQUEST_CHANGES/NO_GO without a structured (JSON
    envelope) reviewer payload, so `_parse_phase_a_findings` returns `[]`
    in the REQUEST_CHANGES/NO_GO branch at `phase_a_executor.py:1266-1268`.
    The pre-revert abort branch incremented `blocking_rounds_in_pass` only
    inside `if blocking:`, so with an empty `blocking` list the counter
    never advanced and the abort never tripped for these tests. Pre-revert
    and post-revert code paths therefore produce identical observable
    results for all three tests — they pass in the current working-tree
    state (verified in A6, `4 passed, 327 deselected`) and must remain
    green through Phase B landing.

    No new test is added in this wave (founder "narrow surgical" directive
    carried forward from v1). Structural proof that the revert restores
    continuation in the *structured-blocking-findings* case is by code
    inspection: there is no remaining early-exit gated on a blocking-round
    counter. The only remaining exits from `_run_bridge_convergence` in
    the current file are:

    - GO converged at `:1232-1234`.
    - GO with unexpected exit code, fail-closed at `:1219-1231`.
    - Non-GO (REQUEST_CHANGES/NO_GO) with exit code not in `(0, 1)`,
      fail-closed at `:1240-1252`.
    - Non-blocking-only GO at `:1297-1304`.
    - STALE/SYNTHETIC/non-{GO,REQUEST_CHANGES,NO_GO} decision with
      matching non-zero exit, fail-closed at `:1440-1450`.
    - STALE/SYNTHETIC decision, fail-closed at `:1451-1462`.
    - Unrecognized-decision fail-closed at `:1463-1481`.
    - Non-zero bridge exit without rendered output at `:1482-1495`.
    - Per-iteration `round_num >= max_bridge_rounds` at `:1497-1500`.
    - Loop-exit `max_rounds_reached` at `:1502-1508`.

    All are unchanged by this wave; none is gated on blocking-round count.

## 3. Constraints (out of scope)

- `max_bridge_rounds` 15-round outer ceiling — unchanged (loop header at
  `phase_a_executor.py:1202`, log line at `:1204` untouched).
- `mu/tools/executors/executor_config.json` — no config changes.
- `mu/tools/executors/phase_b_executor.py` — no changes.
- `mu/tools/executors/dialectic_executor.py` — no changes.
- REQUEST_CHANGES vs NO_GO semantics refactor — separate wave.
- K-series pager work — separate waves.
- No new tests added (founder "narrow surgical" directive). The existing
  Phase A bridge-loop tests enumerated in W1 remain the regression surface
  and are verified in A6; a new regression targeting the removed
  3-round-abort branch with *structured* blocking findings across 3+ rounds
  is explicitly deferred. The underlying divergent-convergence failure mode
  stays documented at `.claude/rules/learning.md` 2026-04-18 PIPELINE entry
  per TASKS.md:149 evidence_delta clause 2.

## 4. Stop conditions

Phase A plan-lock complete when, against the current working-tree state of
`mu/tools/executors/phase_a_executor.py`, all of the following hold:

- No textual reference to `convergence_budget` or `blocking_rounds_in_pass`
  anywhere in the file (A2).
- No textual reference to `convergence budget` or
  `blocking REQUEST_CHANGES rounds in pass` in comments (A3).
- The file parses (AST) with no syntax errors (A1).
- The `_run_bridge_convergence` loop header at `:1202` still matches
  `range(start_round, max_bridge_rounds + 1)` (A4).
- All three Phase A bridge-loop regression tests enumerated in W1
  (expanding to 4 parametrized cases) pass (A6).
- `git diff --stat` for this wave shows exactly one file modified
  (`mu/tools/executors/phase_a_executor.py`), net deletion, zero additions
  (A5).
- No other file modified by this wave.

Stop before running Phase B / commit. This packet covers Phase A plan lock
only; Phase B will land the already-staged revert via
`commit_executor.py --standalone` per the BOOTSTRAP_PHASE_B_EXCEPTION
carried forward from TASKS.md:149 (§6(b) below).

## 5. Acceptance criteria

A1. AST parse (matches TASKS.md:149 predecessor evidence format):
    `python3 -c "import ast; ast.parse(open('mu/tools/executors/phase_a_executor.py').read()); print('OK')"`
    prints `OK`.

A2. Removed identifiers fully absent (reviewer's exact reproduce command
    from bridge REQUEST_CHANGES 2026-04-19 finding #1; re-running it must
    remain empty):
    `rg -n "convergence_budget|blocking_rounds_in_pass" mu/tools/executors/phase_a_executor.py`
    returns zero matches.

A3. Removed semantics not described in the file (second half of the
    reviewer's finding #1 `rg` command):
    `rg -n "convergence budget|blocking REQUEST_CHANGES rounds in pass" mu/tools/executors/phase_a_executor.py`
    returns zero matches.

A4. Loop ceiling unchanged:
    `rg -n "range\(start_round, max_bridge_rounds \+ 1\)" mu/tools/executors/phase_a_executor.py`
    still matches the loop header at `:1202`.

A5. Surgical diff: `git diff --stat` shows exactly one file modified
    (`mu/tools/executors/phase_a_executor.py`), net deletion, zero
    additions.

A6. Phase A bridge-loop regression tests stay green — all three regression
    tests cited in W1 (addresses bridge REQUEST_CHANGES 2026-04-19 finding
    #2, which flagged v2's two-test `-k` filter as inconsistent with the
    W4 regression surface claim):
    `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_dispatch.py -k "test_request_changes_continues_loop or test_non_go_exit_one_continues_loop or test_all_request_changes_returns_max_rounds_not_success"`
    must print `4 passed, 327 deselected` (three test functions, with
    `test_non_go_exit_one_continues_loop` parametrized over
    REQUEST_CHANGES and NO_GO = 2 cases, totaling 4 collected instances;
    327 deselected matches the full test_executor_dispatch.py collection
    minus these 4). Re-verified in-session 2026-04-19 against the current
    working-tree state: `4 passed, 327 deselected in 0.06s`.

## 6. Grounding / Authorization

### Canonical TASKS.md anchor

TASKS.md:149 — tracker sync note for the predecessor wave
`bridge-convergence-budget-2026-04-18` (PR #796), which landed the 3-round
cap this wave reverts. The note states the guard "inserts [a]
convergence-budget guard between [the] non-blocking-convergence branch and
[the] implementer-invocation branch. At round >= 3 with blocking findings,
returns status=error with clear message instead of continuing to
max_bridge_rounds ceiling." The code this revert removes IS the code
TASKS.md:149 describes inserting.

TASKS.md:149 also establishes two still-applicable authorizations that
carry forward to this revert:

(a) **Autonomous pipeline-fix standing auth** — TASKS.md:149 cites
    "standing auth for autonomous pipeline bug fixes per
    feedback_autonomous_executor_fix.md". The founder judges the 3-round
    cap itself to be a pipeline bug introduced by the predecessor wave,
    bringing this revert within that standing auth.

(b) **BOOTSTRAP_PHASE_B_EXCEPTION catch-22 precedent** — TASKS.md:149:
    "this fix targets the bridge loop itself, so bridge review cannot
    validate the fix — bootstrap-exception via commit_executor
    --standalone is the only landing path". The revert modifies the same
    bridge-loop machinery, so the same exception applies.

### Founder directive (in-session, 2026-04-19)

Founder quote this session: "3 loops are not enough..that's ridicoulous",
directly targeting the 3-round cap TASKS.md:149 landed.

There is no separate TASKS.md entry for this revert wave — grep confirmed:
`rg -n "revert-convergence-budget-2026-04-19|FOUNDER_OVERRIDE:revert-convergence-budget-2026-04-19" TASKS.md`
returns NO_TASKS_MATCH. Authorization derives from the TASKS.md:149 anchors
plus the founder directive above, NOT from a self-asserted FOUNDER_OVERRIDE
token in this packet.

### Governing packet & post-revert behavior

Governing packet: this file. No predecessor control-plane packet (the wave
is a direct revert of merged PR #796). After the revert, the loop at
`phase_a_executor.py:1202` again runs through the full `max_bridge_rounds`
ceiling (15) when REQUEST_CHANGES persists. The secondary fail-closed
branches at `:1440-1481` (STALE/SYNTHETIC, unrecognized-decision, and
non-GO-with-unexpected-exit handling, called out in TASKS.md:149
progress_proof_before as the secondary fail-closed on STALE/malformed-
envelope branches) are unchanged by this wave and remain the only
fail-closed exits from the loop aside from the max-rounds-reached exits
at `:1497-1500` and `:1502-1508`.
