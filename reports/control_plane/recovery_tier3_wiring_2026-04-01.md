# Recovery Tier 3 Wiring — Completed

Date: 2026-04-01 (completed 2026-04-06)
Status: COMPLETED
Task: [RECOVERY-TIER3-WIRING]
Purpose: Complete Tier 3 recovery wiring — needs_phase_b reclassification, 8-layer command denylist, sensitive-path blocking.

## Work Items (9/9 landed)

1. Wire `run_recovery_loop()` into `attempt_recovery()` — LANDED (PR #706)
2. Reclassify `needs_phase_b` to Tier 3 recoverable — LANDED (recovery_gate.py)
3. Fix Tier 2 sequential timeout cap — LANDED (executor_dispatch.py, PR #706)
4. Expand Tier 3 denylist to 8-layer defense-in-depth — LANDED (recovery_gate.py)
5. Block edits to repo-internal sensitive paths — LANDED (recovery_gate.py)
6. Surface command routing through dispatcher recovery — LANDED (PR #706)
7. Process-tree cleanup before timeout retry — LANDED (PR #706)
8. Timeout bump cap re-base on original baseline — LANDED (PR #706)
9. Commit executor pytest gate — LANDED (PR #706)

## Denylist Layers (item 4, 9 rounds adversarial review)

| Layer | What it blocks |
|-------|---------------|
| 1. Shell metacharacters | `;`, `\|`, `&`, backtick, `>`, `<`, `$(`, `${`, `$VAR` |
| 2. Exact-match denylist | `rm -rf`, `git push --force`, etc. |
| 3. Git subcommand patterns | reset/checkout/restore/push/clean/config/fetch/pull/clone/stash with global-option awareness |
| 4. Network egress commands | curl, wget, nc, ssh, rsync, etc. with path-prefix stripping |
| 5. Sensitive host paths | /etc/passwd, /proc, ~/.ssh, ~/.aws |
| 6. Shell wrappers | sh/bash/zsh -c (opaque inner command) |
| 7. Interpreter code exec | python3 -c, node -e, ruby -e with preceding-flag awareness |
| 8. Package managers | pip, npm, yarn, cargo, brew, etc. + dangerous Python modules via -m |

## Evidence

- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_recovery_gate.py -q` — 328 passed
- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_recovery_gate.py -k "needs_phase_b or DangerousGitPatterns or SensitiveRepoPath" --tb=short` — 23 passed
- False-positive verification: `grep curl README.md` → not blocked, `echo npm` → not blocked, `python3 -E script.py` → not blocked
