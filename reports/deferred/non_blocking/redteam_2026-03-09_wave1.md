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
CLAUDE.md documents GraphQL + `--admin` workflow that can bypass review.
**Why not fixed:** This is intentional for a single-admin founder repo. The `--admin` flag
is documented as "only when needed after checks pass and threads are resolved." The founder
IS the admin — there's no bypass risk in a single-user repo. Adding more restrictions would
slow the merge workflow without reducing risk. **No fix planned** — design choice.

## 5. Env var security gate suppression (Adversary)
`RCX_SKIP_AGENT_CHECK=1` / `RCX_SKIP_ADVERSARY_CHECK=1` suppress review in pre-commit hook.
**Why not fixed:** These are local dev convenience flags for the founder. CI never sets them
(checked: no workflow file references these env vars). The pre-commit hook is a local-only
gate — CI uses its own green-gate workflow. Removing them would force the founder to wait
for agent review on every local commit, even for doc-only changes.
**No fix planned** — single-user repo, CI is the real gate.

## 6. Bridge `--dangerously-skip-permissions` (Adversary)
Active bridge config uses `--dangerously-skip-permissions` for Claude subprocess.
**Why not fixed:** The bridge runs locally between Claude Code and Codex. Both are
already trusted agents in the founder's environment. The `--dangerously-skip-permissions`
flag allows Codex to execute commands without prompting — necessary for automated
bridge review. The flag name is intentionally scary as a reminder. Not in example config.
**No fix planned** — local-only tool, founder-controlled environment.

## 7. Bridge authentication (Adversary)
Agent identity determined by config file command. No signing/HMAC.
**Why not fixed:** The bridge is a local tool that runs on the founder's machine. There's
no network exposure — both agents communicate via local SQLite bus. Adding HMAC signing
would add complexity for zero security benefit in a local-only tool. If the bridge ever
becomes network-accessible, authentication would be required.
**No fix planned** — local-only tool with no network exposure. Revisit if bridge goes networked.
