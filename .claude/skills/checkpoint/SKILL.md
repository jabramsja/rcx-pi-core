---
name: checkpoint
description: RCX Decision-Point Self-Check — catches deflection and skipped skills before commit/bridge
---

# /checkpoint — RCX Decision-Point Self-Check

Run this BEFORE every commit and BEFORE every bridge submission. It catches skipped skills, deflection patterns, and missing steps.

## When to Auto-Invoke

- Before `git commit` (the pre-commit hook reminds, but this checks SKILL compliance)
- Before bridge submission
- When about to classify something as "pre-existing" or "out of scope"
- When about to ask the founder "should I fix this?"

## Steps

1. **Deflection check** — Am I about to defer, classify, or ask permission instead of fixing something? If yes, STOP and fix it. Read `feedback_deflection_pattern.md`.

2. **Skill compliance check** — For this session, verify:
   - Did JS or Python runtime files change? → Was `/parity` run? If not, run it now.
   - Did debt markers or STATUS.md debt section change? → Was `/audit ratchets` run? If not, run it now.
   - Were fixes implemented? → Was `/audit fast` run before bridge? If not, run it now.
   - Is this an L4 wave? → Was `/tracker` run? If not, run it now.

3. **Bridge finding check** — If bridge returned NO_GO:
   - Are ALL findings classified correctly? Blockers in `blocking/`, non-blockers in `non_blocking/`.
   - Did I fix every finding the bridge flagged? Not demote them?
   - Did I re-submit to bridge after fixes?

4. **Blocker scan** — `ls reports/deferred/blocking/` — are there ANY unresolved blockers? If yes, they must be fixed before commit.

5. **Report** — Output a one-line pass/fail for each check.

## Output Format

```
CHECKPOINT
Deflection: <clean / CAUGHT: was about to defer X>
Skills: /parity <ran/SKIPPED> | /audit <ran/SKIPPED> | /debt <ran/SKIPPED> | /tracker <ran/N/A>
Bridge: <converged/NO_GO pending/N/A>
Blockers: <0 unresolved / N UNRESOLVED>
```
