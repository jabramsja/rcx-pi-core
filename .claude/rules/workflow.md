---
description: "Branching, PR merge, and audit tier rules"
globs: ["tools/audit_*", "tools/pre-*", "tools/merge_pr.sh"]
---

**Branching:** `dev` is primary. All PRs target `dev`. No `main` in active use.

**PR merge:** Bot auto-reviews. READ comments before resolving. Use `commit_executor.py` for the full commit-through-merge pipeline. The executor calls `merge_pr.sh` internally — do not invoke it manually as a standalone step.

**Audit tiers:**

| Tier | Script | When |
|------|--------|------|
| 1 | `./tools/audit_fast.sh` | Local iteration (~3 min) |
| 2 | `./tools/audit_all.sh` | Before push (~5-8 min) |
| 3 | CI green gate | Push/PR to dev (~2 min) |
| 4-5 | CI nightly/weekly | Scheduled |

**Per-commit gate:** `pre-push-fast` runs automatically during push (audit_fast + L4 contract). In the automated `commit_executor.py` path, Step 11 runs `pre-push-fast` explicitly before Step 12, so Step 12 uses `git push --no-verify` only to avoid rerunning the same hook on the same local HEAD. Outside that bounded executor path, do not use `--no-verify`. `audit_all.sh` is for thorough pre-release validation, not per-commit.
