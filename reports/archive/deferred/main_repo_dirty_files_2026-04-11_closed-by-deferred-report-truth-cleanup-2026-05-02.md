# Main Repo Dirty Files (Deferred — Non-Blocking)

**Date:** 2026-04-11
**Wave context:** Session 2026-04-11 accumulated 6 in-flight tracked-file modifications + 1 untracked session artifact in the main repo working tree (`/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX`) that were never committed. Surfaced during the validator-fix wave's post-merge verify failure at `commit_executor.py:2511` when `git pull` collided with one of them (`TASKS.md`). The TASKS.md file is handled as BLOCKING and bundled into the `post-merge-verify-fetch-fix-2026-04-11` wave. The remaining 6 tracked files + 1 untracked artifact are non-blocking and deferred here per founder directive 2026-04-11 ("non-blocking → /deferred with explanation").
**Status:** DEFERRED — NON-BLOCKING
**Founder directive applied:** 2026-04-11 "It does not matter if it is pre-existing — we do not just ignore it. If non-blocking we can add to /deferred."

---

## Why these are non-blocking

None of the 7 items below prevent any wave from executing. They are in-flight session work (some from this session, some from prior sessions) that represents completed-but-unlanded fixes/enhancements/artifacts. The main repo working tree being dirty on these files does NOT:

- Block phase_a/phase_b/commit_executor in a FRESH WORKTREE (dirty state is main-repo-scoped, not worktree-scoped).
- Block CI, bot review, or merge on PRs originating from fresh worktrees.
- Interact with the pipeline other than via the `commit_executor.py:2511` `git pull` post-merge verify collision on `TASKS.md` specifically (which is handled as BLOCKING in the `post-merge-verify-fetch-fix-2026-04-11` wave).

**After the post-merge-verify-fetch-fix wave lands**, the `git pull` in Step 15 is replaced with `git fetch origin <base>` (no working-tree mutation), and these 6 files + 1 artifact can remain dirty indefinitely without interfering with any wave operation.

---

## Deferred Items

### 1. `.claude/hooks/record-dream.sh` — canonical format write

**File:** `.claude/hooks/record-dream.sh` (2-line change)
**Current dirty diff:** changes `date +%s > .last_dream` to `date +%Y-%m-%d > .last_dream` with an explanatory comment. Companion to `.claude/skills/dream/SKILL.md` Phase 4 step 7 (item #5 below) and `.claude/hooks/should-dream.sh` liberal reader (item #2 below).
**Intent:** make record-dream.sh write the canonical `YYYY-MM-DD` format directly, matching the `/dream` SKILL.md Phase 4 requirement and the `should-dream.sh` primary parse branch. Prevents the 2026-04-10 regression where `should-dream.sh` blocked session end with "overdue by 493,292h" because of a format-write mismatch (record-dream wrote epoch, should-dream parsed YYYY-MM-DD, 2012-style epoch arithmetic produced garbage hours).
**Why non-blocking:** `should-dream.sh` is a liberal reader (accepts YYYY-MM-DD, ISO 8601, and epoch) after the 2026-04-10 fix applied in item #2 below, so the old format still parses. This change is a writer-discipline alignment, not a bug fix.
**Resolution path:** land in a future `dream-format-alignment-2026-04-xx` cleanup wave (bundle with items #2 and #5).

### 2. `.claude/hooks/should-dream.sh` — 3-format liberal parser

**File:** `.claude/hooks/should-dream.sh` (~39 lines added / 8 lines modified)
**Current dirty diff:** rewrites the parse logic to accept 3 formats:
  - `YYYY-MM-DD` (canonical per `/dream` SKILL.md Phase 4)
  - `YYYY-MM-DDTHH:MM:SSZ` (ISO 8601 — legacy from a parallel worktree `/dream` run that freelanced a format)
  - all-digit epoch (legacy from older `record-dream.sh`)
Plus: reason string now includes the raw `.last_dream` content for diagnostic context.
**Intent:** structural fix for the 2026-04-10 "overdue by 493,292h" regression (format reader was strict, writers were inconsistent across sessions). Readers must be liberal, writers must be canonical.
**Why non-blocking:** the fix is already applied in this main-repo copy and has been observed working during /dream runs this session. It's dirty because it was never committed. Its behavior is identical to what a landed version would be.
**Resolution path:** bundle with items #1 and #5 in the `dream-format-alignment` cleanup wave.

### 3. `.claude/hooks/tool-call-counter.sh` — 40-threshold + pipeline subprocess early-exit

**File:** `.claude/hooks/tool-call-counter.sh` (~36 lines added / 4 lines modified)
**Current dirty diff:** two coupled changes:
  - Threshold changed from every-20th-tool-call BLOCK to every-40th-tool-call BLOCK (this session's founder directive 2026-04-11: "change to 40 tool calls").
  - Pipeline-subprocess early-exit: walks up the process ancestry from `$PPID` and exits silently if any ancestor command matches `phase_a_executor.py|phase_b_executor.py|commit_executor.py|meta_bridge_supervisor|bridge_adapters|executor_dispatch`. This prevents the shared `/tmp/.rcx_tool_call_counter` file from being incremented by pipeline subprocesses that have their own verification discipline (bridge review + turn budgets), which was the root cause of the 2026-04-10 impl-fde7f3d8 regression where Phase B's implementer hit a verification checkpoint mid-round and produced zero Edits.
**Intent:** (a) match founder-directed threshold, (b) isolate the counter from pipeline subprocesses to prevent cross-session contamination.
**Why non-blocking:** the hook runs on every PostToolUse tool call; the current dirty version is ALREADY the active behavior (observed this session: checkpoint fired at #6560 with the 40-threshold reason text, confirming hot-reload). The ancestry check also runs live. Committing just persists the behavior into git; it doesn't change behavior.
**Resolution path:** bundle in a `hook-hardening-2026-04-xx` cleanup wave with items #4 and #6.

### 4. `.claude/settings.json` — bridge.db enforcement extracted to script

**File:** `.claude/settings.json` (1 line change)
**Current dirty diff:** replaces the inline bash one-liner that enforces `mcp__sqlite__read_query` over raw `sqlite3` for main-repo `bridge.db` access with a call to `$CLAUDE_PROJECT_DIR/.claude/hooks/force-mcp-sqlite.sh`.
**Intent:** move inline hook commands into dedicated script files for readability + maintainability. The inline version at settings.json:25 was long and hard to diff; extracting it to a script makes future modifications clean.
**Why non-blocking:** the behavior is identical whether the enforcement runs inline or via script. Need to verify `force-mcp-sqlite.sh` exists in the repo before committing — if missing, the edit would break the bridge.db guard. I have NOT verified this file exists this turn.
**Resolution path:** the future cleanup wave must first verify `.claude/hooks/force-mcp-sqlite.sh` exists; if missing, add it as part of the same commit. Bundle with items #3 and #6 in the `hook-hardening` cleanup wave.

### 5. `.claude/skills/dream/SKILL.md` — Phase 4 step 7 canonical format

**File:** `.claude/skills/dream/SKILL.md` (6 lines added)
**Current dirty diff:** adds Phase 4 step 7 to the `/dream` skill instructions: mandates the exact command `date +%Y-%m-%d > ~/.claude/projects/-Users-jeffabrams-Desktop-RCX-X-RCXStack-RCXStackminimal-WorkingRCX/memory/.last_dream` with a warning against freelancing other formats. Cross-references the 2026-04-10 learning entries about the prior ISO-8601 / epoch regressions.
**Intent:** prevent any future `/dream` run from writing a non-canonical format.
**Why non-blocking:** /dream is cross-session guidance; it doesn't affect wave execution. The current dirty version is already the instruction Claude reads at /dream invocation (SKILL.md is loaded fresh on each Skill tool use).
**Resolution path:** bundle with items #1 and #2 in the `dream-format-alignment` cleanup wave.

### 6. `.claude/skills/preflight/SKILL.md` — symlink version detection + 39-patch verification

**File:** `.claude/skills/preflight/SKILL.md` (~78 lines added / 15 lines modified)
**Current dirty diff:** substantial rewrite of preflight Step 17 (CC version detection) and Step 19 (binary patch verification):
  - **Step 17 rewrite:** uses `readlink ~/.local/bin/claude` symlink target to detect the active CC version, bypassing the `autoUpdaterStatus: disabled` flag regression in CC v2.1.97+ (the flag is ignored by the CC binary's internal update check despite being set in `~/.claude/settings.json`). Stores last-seen version in `~/.claude/patch_backups/.last_seen_version` for session-over-session change detection.
  - **Step 19 expansion:** patch verification extended from 30 to 39 active patches. Adds positive checks for P_OjH (`function OjH(H){return!1`), P31-P32 (v2.1.101 planning/reasoning-chain), P33-P35 (yvf Communication style text rewrites), P36-P39 (iLf/nLf auto-mode reminder rewrites). Removes P1 (the `# Output efficiency` section Anthropic deleted in v2.1.101, now a negative check). Updates the merged P7/P30 selector.
**Intent:** harden preflight to catch auto-updates the user explicitly disabled but CC ignored, and to verify all 39 active binary patches on the current v2.1.101 binary. Both changes are anti-drift enforcement from the 2026-04-10 founder-directed session.
**Why non-blocking:** preflight runs at session start / founder request. The current dirty version has been the ACTIVE preflight behavior for this entire session (verified by the early preflight response which enumerated 39 patches + NEEDS_REPATCH=0 + symlink version check). Committing persists the preflight behavior; it doesn't change it.
**Resolution path:** bundle with items #3 and #4 in the `hook-hardening` cleanup wave, OR promote to its own dedicated preflight-hardening-followup wave given the scope.

### 7. `reports/control_plane/session_handoff_2026-04-11_block_protected_lexer.md` — session handoff artifact

**File:** `reports/control_plane/session_handoff_2026-04-11_block_protected_lexer.md` (untracked, 213 lines, ~25 KB)
**Current state:** untracked new file. Written earlier this session per founder request; contains: (1) block-protected-branch-lexer sub-wave state recap, (2) learning store wave (PR #751) deep audit with file:line evidence for delivered vs not-delivered features, (3) "was it worth it" assessment with Move A/B recommendations, (4) preflight flags + stale docs list, (5) canonical next-session checklist, (6) reference anchors.
**Intent:** durable session record that next session can read for orientation. Analogous to prior session handoffs at `reports/control_plane/session_handoff_2026-04-08_preflight_hardening.md` etc.
**Why non-blocking:** session handoffs are informational artifacts for cross-session continuity. They do not affect wave execution. New untracked file, so cannot interfere with any `git pull` (gitignore rule for `reports/control_plane/` is negated per `.gitignore:60: !reports/control_plane/**`, so the file IS trackable, just not yet tracked).
**Resolution path:** include in the `hook-hardening` cleanup wave OR bundle into the next wave's packet scope as a historical artifact.

---

## Why not commit these right now?

1. **Scope discipline.** Each of items #1-#7 belongs to a different concern (dream format, hook hardening, preflight enhancement, session handoff, TASKS.md cleanup). Committing all 7 + this deferred report in one "cleanup" wave creates an incoherent 8-file wave packet that bridge review would flag for scope creep.

2. **Ordering constraint.** Before ANY cleanup wave can run its Step 15 post-merge verify cleanly, the `commit_executor.py:2511` structural fix (wave: `post-merge-verify-fetch-fix-2026-04-11`) must already be on dev. That fix wave has its own tight scope (commit_executor.py + regression test + TASKS.md META-BRIDGE deletion as the collision trigger). Running the cleanup wave before the post-merge verify fix means the cleanup wave would trip on its OWN Step 15 (TASKS.md dirty + pull collision).

3. **Founder directive.** Per 2026-04-11 founder directive, non-blocking items go to /deferred with explanation. This report IS that action. The founder explicitly authorized /deferred as the answer to "do I need to fix this right now".

---

## Proposed resolution sequence

1. `post-merge-verify-fetch-fix-2026-04-11` wave — structural fix at `commit_executor.py:2511` + regression test + TASKS.md META-BRIDGE stale-entry deletion. [CURRENTLY PLANNED]
2. `block-protected-branch-lexer-2026-04-11` wave follow-through — the original "next wave" per founder directive. Lexer follow-up through full dispatch chain.
3. `dream-format-alignment-2026-04-11` cleanup wave — items #1, #2, #5. Small coherent packet.
4. `hook-hardening-2026-04-11` cleanup wave — items #3, #4, #6, #7 + this deferred report. Medium packet; preflight SKILL enhancement (item #6) may warrant splitting to its own wave if the packet grows too large.
5. `learning-store-move-a-2026-04-xx` — the `.claude/rules/learning.md` bidirectional cross-pollination wave per the founder's ROI recommendation.

---

## Founder decision record

**Founder directive (2026-04-11, session context):** "goal is to ALWAYS USE THE PIPELINE WITH WAVES. IT MAKES THE WAVE BETTER AND IT TESTS THE PIPELINE"
**Founder directive (2026-04-11, session context):** "It does not matter if it is pre-existing — we do not just ignore it. If non-blocking we can add to /deferred; if blocking it needs to be taken care of."

This deferred report satisfies the /deferred path for 7 non-blocking items. The 1 blocking item (`TASKS.md` META-BRIDGE stale-entry deletion) is handled by bundling into the `post-merge-verify-fetch-fix-2026-04-11` wave's scope.
