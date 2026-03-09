# Wave 1 (Docs) — Deferred Non-Blockers

**Date:** 2026-03-09
**Source:** Agent red-team (structural-proof, expert, adversary, verifier) + bridge review (Codex)

---

## 1. ROADMAP.md duplication (Expert)
ROADMAP.md (41 lines) duplicates the reading order from `roadmap/MANIFEST.md` (11 items vs MANIFEST's 13). Could be collapsed to a 5-line pointer. Not a false claim — just stale duplication.

## 2. TASKS.md Ra section bloat (Expert)
Ra section consumes 494/743 lines (66%). Navigation friction for active task sections. Suggest adding a TOC header with line anchors. Not structural — aesthetic.

## 3. GraphQL thread-resolve governance bypass (Adversary)
CLAUDE.md documents GraphQL + `--admin` workflow that can bypass review. This is intentional for single-admin founder repo. Design choice, not vulnerability.

## 4. `--admin` vs CI_POLICY.md contradiction (Adversary)
CLAUDE.md documents `gh pr merge --admin`; CI_POLICY.md claims "Branch protection cannot be bypassed." Needs founder decision on reconciliation. POLICY_BOUND.

## 5. Env var security gate suppression (Adversary)
`RCX_SKIP_AGENT_CHECK=1` / `RCX_SKIP_ADVERSARY_CHECK=1` suppress review in pre-commit hook. Documented, single-user repo, non-blocking by design.

## 6. Bridge `--dangerously-skip-permissions` (Adversary)
Active bridge config uses `--dangerously-skip-permissions` for Claude subprocess. Not in example config. Founder's local dev choice.

## 7. Bridge authentication (Adversary)
Agent identity determined by config file command. No signing/HMAC. Local-only tool with no network exposure.
