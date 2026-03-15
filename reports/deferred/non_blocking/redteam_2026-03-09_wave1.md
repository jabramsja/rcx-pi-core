# Wave 1 (Docs) — Deferred Non-Blockers

**Date:** 2026-03-09
**Source:** Agent red-team (structural-proof, expert, adversary, verifier) + bridge review (Codex)

Archived from the source snapshot as resolved:

- TASKS.md Ra section bloat (resolved 2026-03-13 during tracker compaction)
- `--admin` vs CI policy contradiction (resolved 2026-03-14 by aligning
  `CLAUDE.md` and `mu/docs/audit/CI_POLICY.md` to "admin only when needed")

---

## 1. ROADMAP.md duplication (Expert) — RESOLVED (2026-03-14)
Reading order collapsed to single-line pointer to `roadmap/MANIFEST.md`. ROADMAP.md now 30 lines.

## 3. GraphQL thread-resolve governance bypass (Adversary)
CLAUDE.md documents GraphQL + `--admin` workflow that can bypass review. This is intentional for single-admin founder repo. Design choice, not vulnerability.

## 5. Env var security gate suppression (Adversary)
`RCX_SKIP_AGENT_CHECK=1` / `RCX_SKIP_ADVERSARY_CHECK=1` suppress review in pre-commit hook. Documented, single-user repo, non-blocking by design.

## 6. Bridge `--dangerously-skip-permissions` (Adversary)
Active bridge config uses `--dangerously-skip-permissions` for Claude subprocess. Not in example config. Founder's local dev choice.

## 7. Bridge authentication (Adversary)
Agent identity determined by config file command. No signing/HMAC. Local-only tool with no network exposure.
