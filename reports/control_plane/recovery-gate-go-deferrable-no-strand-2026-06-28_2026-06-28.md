# Recovery gate: a bridge GO with only deferrable findings proceeds, not tier3-exhaust-strand

Date: 2026-06-28
Status: Phase B (locked, implementing)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: recovery-gate-go-deferrable-no-strand-2026-06-28
Phase-A-Lock: LOCKED
Purpose: STOP the recurring strand where a Phase-B wave the bridge GO'd still fails-closed-exhausts in tier-3 recovery, forcing a manual hand-finish. SYMPTOM (verified, recurred on THREE waves this session -- claude-roles linchpin, single-orchestrator-switch, pager-default): the bridge returns decision=GO for the round, but attaches one or more findings whose disposition field is 'blocking' even though they are LOW-severity / reviewer-acknowledged / deferrable (e.g. 'no dedicated regression test for X', a doc-accuracy nit). The recovery consistency-check then classifies this GO-with-blocking-disposition as failure_class=agent_review_crash (recovery_gate.classify_failure, via the broad 'reviewer'/'bridge' hint branches), and the tier-3 recovery delegate cannot resolve a GO-with-deferrable-findings, so it runs to tier3_exhausted and strands the wave with NO commit. GOAL: when the bridge decision is GO and the attached findings are ALL low-severity / non-blocking-class / reviewer-acknowledged (deferrable), the wave must PROCEED to commit -- filing those findings as deferred non-blockers (reports/deferred/non_blocking) -- NOT classify agent_review_crash and exhaust. ONLY a genuine NO_GO, or a GO that carries a HIGH-severity / true-blocking finding, may route to recovery/strand (do NOT weaken those). The implementer must LOCATE the exact code that produces the GO-with-blocking-disposition failure -- recovery_gate.classify_failure (the agent_review_crash classification) AND whatever upstream emits the status=failed / disposition=blocking verdict on a GO round -- and fix it so a GO-with-only-deferrable-findings defers + proceeds. Add a regression to test_recovery_gate.py covering: GO + low/non-blocking-disposition finding => proceed (no agent_review_crash, no tier3 exhaust); and GO + high/blocking finding => still strands. STRICT SCOPE: recovery_gate + its test only (+ the upstream verdict-emit if needed); no host semantics; do NOT weaken genuine NO_GO or high-severity blocking strands.

## Scope

STOP the recurring strand where a Phase-B wave the bridge GO'd still fails-closed-exhausts in tier-3 recovery, forcing a manual hand-finish. SYMPTOM (verified, recurred on THREE waves this session -- claude-roles linchpin, single-orchestrator-switch, pager-default): the bridge returns decision=GO for the round, but attaches one or more findings whose disposition field is 'blocking' even though they are LOW-severity / reviewer-acknowledged / deferrable (e.g. 'no dedicated regression test for X', a doc-accuracy nit). The recovery consistency-check then classifies this GO-with-blocking-disposition as failure_class=agent_review_crash (recovery_gate.classify_failure, via the broad 'reviewer'/'bridge' hint branches), and the tier-3 recovery delegate cannot resolve a GO-with-deferrable-findings, so it runs to tier3_exhausted and strands the wave with NO commit. GOAL: when the bridge decision is GO and the attached findings are ALL low-severity / non-blocking-class / reviewer-acknowledged (deferrable), the wave must PROCEED to commit -- filing those findings as deferred non-blockers (reports/deferred/non_blocking) -- NOT classify agent_review_crash and exhaust. ONLY a genuine NO_GO, or a GO that carries a HIGH-severity / true-blocking finding, may route to recovery/strand (do NOT weaken those). The implementer must LOCATE the exact code that produces the GO-with-blocking-disposition failure -- recovery_gate.classify_failure (the agent_review_crash classification) AND whatever upstream emits the status=failed / disposition=blocking verdict on a GO round -- and fix it so a GO-with-only-deferrable-findings defers + proceeds. Add a regression to test_recovery_gate.py covering: GO + low/non-blocking-disposition finding => proceed (no agent_review_crash, no tier3 exhaust); and GO + high/blocking finding => still strands. STRICT SCOPE: recovery_gate + its test only (+ the upstream verdict-emit if needed); no host semantics; do NOT weaken genuine NO_GO or high-severity blocking strands.

Files and surfaces in scope:

- `mu/tools/executors/recovery_gate.py` -- holds `classify_failure`, where a bridge GO-with-blocking-disposition finding is currently misclassified `AGENT_REVIEW_CRASH` (the broad `review_crash_hints` / `agent`/`bridge` branches). PRIMARY change surface.
- `mu/tests/tools/test_recovery_gate.py` -- regression target named by `evidence_command`; gains the GO+deferrable => proceed and GO+high/blocking => strand cases.
- TASKS.md -- tracker-sync authority. The 2026-06-28 tracker sync note for wave `recovery-gate-go-deferrable-no-strand-2026-06-28` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Locate the exact classification that turns a bridge GO-with-blocking-disposition finding into a strand. VERIFIED current code truth (2026-06-28): `recovery_gate.classify_failure` routes any `status_failed` result whose combined text matches the broad `review_crash_hints` tuple (which includes the bare substring `"reviewer"`), or whose step contains `"agent"`/`"bridge"`, to `FailureClass.AGENT_REVIEW_CRASH` (Tier 3). No branch currently inspects the bridge `decision`, finding `severity`, or finding `disposition`, so a GO round carrying a low/deferrable finding falls into the same agent_review_crash -> tier3 path as a real reviewer crash and exhausts. (Confirmed still unlanded: `recovery_gate.py` has no `deferrable`/`disposition`/`decision==GO` handling, and `test_recovery_gate.py` has no such regression.)
2. Add a deferrable-GO guard to `classify_failure` ahead of the broad review-crash branches: when the result represents a bridge round whose decision is GO and whose findings are ALL low-severity / non-blocking-class / reviewer-acknowledged (deferrable), it must NOT return `FailureClass.AGENT_REVIEW_CRASH`. The classification must put the round on the defer-and-proceed-to-commit path (findings filed as deferred non-blockers under `reports/deferred/non_blocking`), not the tier3 recovery/strand path. The guard fires ONLY on decision=GO with zero high-severity / true-blocking-disposition findings.
3. Preserve the existing strand paths unchanged: a genuine NO_GO, and a GO carrying any high-severity / true-blocking-disposition finding, must still classify into the recovery/strand path. Do not broaden or weaken the existing `review_crash_hints` / `agent`/`bridge` branches for real reviewer/agent/bridge crashes.
4. Add a regression to `mu/tests/tools/test_recovery_gate.py` covering both directions: (a) GO + a low/non-blocking-disposition finding => proceeds (not `AGENT_REVIEW_CRASH`, no tier3 exhaust); (b) GO + a high/true-blocking finding => still strands; plus a sanity case that a genuine NO_GO => still strands.

## Constraints

- STRICT SCOPE: modify only `mu/tools/executors/recovery_gate.py` (the `classify_failure` classification) and `mu/tests/tools/test_recovery_gate.py` (regression). Do not touch any other executor, the bridge, or the Phase B / commit surfaces.
- L4_ENABLER (target_gate_id G8): MUST NOT touch runtime/substrate dirs (`rcx_pi/selfhost/`, `mu/host/`). `recovery_gate.py` is control-plane tooling, not runtime -- keep it that way.
- No host semantics: the fix is pure classification logic over the existing result dict; add no new host-only capability.
- Do NOT weaken genuine NO_GO detection.
- Do NOT weaken GO-with-high-severity / true-blocking-disposition detection. The deferrable guard must fire ONLY on decision=GO with zero high/blocking findings.
- Do NOT broaden the existing review-crash hints such that real reviewer/agent/bridge crashes stop classifying as `AGENT_REVIEW_CRASH`.

## Stop conditions

- If letting a deferrable GO proceed cannot be done without also letting a genuine NO_GO or a high/blocking GO proceed, STOP -- the guard is wrong; surface as POLICY_BOUND rather than weaken a real strand.
- If resolving the misclassification requires modifying any file beyond `recovery_gate.py` + `test_recovery_gate.py` (e.g. an upstream verdict-emit surface that stamps status=failed / disposition=blocking on a GO round), STOP and re-scope through the founder -- do not silently widen staged scope past the tracker-note evidence surface.
- If the change would require adding host semantics or touching a runtime/substrate dir, STOP (L4_ENABLER violation).
- If `evidence_command` is not green after the change, do NOT commit.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_recovery_gate.py`

## Acceptance criteria

- `classify_failure` for a bridge GO whose findings are ALL low-severity / non-blocking-class / reviewer-acknowledged does NOT return `FailureClass.AGENT_REVIEW_CRASH`; the round defers its findings and proceeds to commit (no tier3 exhaust, no strand).
- `classify_failure` for a genuine NO_GO still routes to the recovery/strand path (unchanged).
- `classify_failure` for a GO carrying any high-severity / true-blocking-disposition finding still strands (unchanged).
- `mu/tests/tools/test_recovery_gate.py` contains a new regression asserting BOTH directions (GO+deferrable => proceed; GO+high/blocking => strand) and it passes.
- `evidence_command` is green: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_recovery_gate.py`.
- Staged scope at commit is limited to `recovery_gate.py` + `test_recovery_gate.py` (+ the TASKS.md tracker note), matching the in-scope declaration so the L4 staged-scope check passes.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `recovery-gate-go-deferrable-no-strand-2026-06-28`.
- Governing packet: this file, `reports/control_plane/recovery-gate-go-deferrable-no-strand-2026-06-28_2026-06-28.md`.
- TASKS.md authority: the 2026-06-28 tracker sync note for wave `recovery-gate-go-deferrable-no-strand-2026-06-28` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:recovery-gate-go-deferrable-no-strand-2026-06-28
