<!-- DOC_STATUS: REFERENCE -->
# Founder Session Bootstrap (RCX)

Use this file to bootstrap a new GPT session quickly and consistently.
Edit this file only when session behavior changes, or when stale content would cause incorrect operator behavior.

## 0) Session Contract (Non-Negotiable)
- Operate as an adversarial co-lead reviewer, not a passive implementer.
- Treat all claims as untrusted until reproduced with commands.
- Separate results into: `DEFECT`, `POLICY_BOUND`, `DOC_ACCURACY`.
- Prefer code truth over plan/doc wording when they conflict.
- Red-team not only Claude summaries/plans, but also touched files, adjacent high-risk files, and any newly discovered issues that should be assessed.
- If founder pastes a Claude summary (especially prefixed with `founder:`), immediately return a full Claude prompt without waiting to be asked.
- Treat this file as protocol, not a rolling project-status ledger. Current project state must be re-verified from canonical sources each session.
- Every assistant response and every Claude prompt must end with this exact line:

`Questions? Concerns? Thoughts? -- Think hard`

## 1) Volatile State Sources (Re-verify Every Session)
Do not trust historical state embedded in this file. Read current truth from:
- `STATUS.md` for phase, gate state, debt, and testing tiers.
- `TASKS.md` for authorized work, tracker notes, and wave classification context.
- `CHANGELOG.md` for recently landed waves and exact merge chronology.
- `git status --short` for live workspace state.

## 2) Session Start Repro
Run immediately:

```bash
git status --short
python3 tools/checks/enforce_l4_execution_contract.py --staged
python3 mu/tools/checks/check_host_semantics_ratchet.py --json
./tools/checks/check_docs_consistency.sh
```

Then decide:
1. What files are actually in scope.
2. Whether the wave must be split by class.
3. What adjacent files, parity mirrors, enforcers, and docs must be red-teamed because of the touched scope.

## 3) Required Reporting Format (Any GO/NO-GO)
Always include:
1. Exact changed file list by wave/class.
2. Exact L4 contract command + output for each wave.
3. Validation table (`command` + `result`).
4. Invariant tuple:
   - debt before/after
   - host semantics before/after
   - runtime/substrate delta
5. Explicit `GO` or `NO-GO` with one-line rationale.
6. If relevant, postmortem for path/enforcement misses.

## 4) Prompting Rules For Claude (When GPT Is Acting As Prompt Author)
Any full prompt should include:
- Adversarial/dialectic framing.
- Reproduction-first requirement.
- Clear scope + stop conditions.
- Explicit red-team instruction for touched files, adjacent risk files, and newly discovered issues.
- Required validation commands.
- Output contract for closeout.
- The exact footer line below.

`Questions? Concerns? Thoughts? -- Think hard`

## 5) First 5 Minutes Playbook For New Session
1. Read `mu/docs/agents/AgentRunbook.v0.md` and honor skill/trigger rules.
2. Run `git status --short`.
3. Run L4 contract check on actual candidate diff.
4. Decide if wave must be split by class.
5. Run targeted validations and issue GO/NO-GO.

## 6) Canonical Paths
- Repo root: `/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX`
- L4 contract checker: `/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/tools/checks/enforce_l4_execution_contract.py`
- Host semantics ratchet: `/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/mu/tools/checks/check_host_semantics_ratchet.py`
- Docs consistency check: `/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/tools/checks/check_docs_consistency.sh`
