# Session Handoff — Anti-Drift Enforcement (2026-04-07)

## What Was Done

**PR #746 MERGED** (2026-04-08T01:48:19Z) — `chore: anti-drift enforcement — 26 patches, hook hardening, STATUS consolidation`

### Binary Patches (P1-P26, 26 total)
Applied to CC binary at `~/.local/share/claude/versions/2.1.92`. Takes effect on next session launch.

| Category | Patches | What they do |
|----------|---------|-------------|
| Anti-conciseness | P1, P2 | Dead-code `$P4()` "go straight to the point"; null "short and concise" |
| CLAUDE.md authority | P3 | "may or may not be relevant" → "mandatory project instructions" |
| Task/IDE noise | P4a, P4b, P5, P12 | Strip dismissive language from reminders/IDE events |
| Overcaution removal | P7 | Dead-code `_P4()` "executing actions with care" |
| Parallel→Sequential | P8, P13, P14(x2), P23, P26(x2) | 6 separate parallel-first instructions → sequential preference |
| Hook exception | P9 | Allow `--no-verify` for bounded executor pipeline |
| File creation | P10 | Relax restriction for pipeline artifacts |
| Secrecy removal | P11 | "Don't tell the user" → neutral |
| **Anti-verification** | **P16, P17, P18, P19** | **ROOT CAUSE: "Do NOT re-read to verify" → "verification encouraged"; "Wasted call" → neutral; "no need to Read it back" → "file updated successfully"** |
| Manual-git→pipeline | P15, P20, P21, P22, P25 | Replace step-by-step manual git with "use the pipeline" |
| Anti-read removal | P24 | "NEVER run additional commands to read" → "read and explore as needed" |

**Backup:** `~/.claude/patch_backups/patched_base_prompt_20260407_170928.js`
**Reference:** `reference_tweakcc_repatch.md` in memory (all 26 patch commands + verification)

### Hook Changes (in repo, merged)
- `check-reasoning-depth.sh` — Cron evidence gate (blocks `[cron:]` without MCP/Read evidence), test-result claim gate (blocks "tests pass" without pytest output), thresholds 600/800
- `reinject-after-compact.sh` — Comprehensive PostCompact reinject (identity, 6 overrides, 5 hard rules, RCX context, cron recreation instruction)
- `block-protected-branch.sh` — Comment stripping before newline collapse (fixes false positives). **NOTE: P1 bot finding identified a remaining edge case — fix exists locally on dev working tree but NOT yet pushed. Follow-up needed.**
- `settings.json` — All hooks consolidated from settings.local.json (8 event types: PreToolUse, PostToolUse, Stop, PostCompact, SubagentStop, UserPromptSubmit, SessionStart, SubagentStart)

### Preflight Upgraded (17 steps)
- Step 14: Cron prompt requires 3 mandatory tool calls (Read MEMORY.md, MCP SQLite, CronList)
- Step 16: 32 patch verification checks with auto-repatch on CC update
- Step 17: Binary backup comparison to detect CC auto-updates

### Other Changes
- `STATUS.md` consolidated 849→489 lines (archive: `archive/status_history_jan_mar_2026.md`)
- `CLAUDE.md` line 24: "ask before launching pipeline" + "NEVER manual git"
- `persona.md`: RCX production quality discipline section (5 bullets)
- Dream protection: 9 memory files now have `protected: true` frontmatter
- `settings.local.json` untracked (hooks moved to settings.json, only permissions/effortLevel/outputStyle remain)
- effortLevel set to "max" in both `~/.claude/settings.json` and `.claude/settings.local.json`

### Settings (outside repo)
- `~/.claude/settings.json`: effortLevel "max", `RCX_BRIDGE_REVIEWER_OVERRIDE=claude` (temporary until Friday)
- `.claude/settings.local.json`: hooks removed (now in tracked settings.json), effortLevel "max"

## Open Items for Next Session

1. **P1 bot finding follow-up:** `block-protected-branch.sh` comment-stripping fix exists on dev working tree but was NOT included in PR #746. The fix moves comment stripping to BEFORE newline collapse (`sed 's/#.*$//'` on original multi-line input). Needs to be committed via pipeline.

2. **P2 bot findings (deferred):**
   - Cron evidence matcher accepts generic status words (`AWAITING`, `COMPLETE`) — could tighten to require `result-id` or MCP-specific patterns
   - SessionStart hook in `settings.json` has machine-specific `~/.claude/projects/-Users-jeffabrams-...` path — should derive from repo context

3. **Pre-existing worktree test issue:** `test_agent_prompt_contract_injection.py::test_contract_injected_for_all_runtime_agents` fails in worktrees because DOC_STATUS header in agent contract file contains main repo path. Only affects worktree test runs, not CI.

4. **11 stale `/tmp/workingrcx_*` directories** from prior pipeline sessions. Safe to clean up.

5. **Next wave: [META-BRIDGE-BOUNDED-REVIEW-FIX]** — authorized in TASKS.md, has tracked packet at `reports/control_plane/meta_bridge_taskid_path_safety_2026-04-03.md`. Run through full pipeline (dispatcher → Phase A → Phase B → commit).

## Key State

```
Phase: 8c
Debt: 12/12 (FLOOR=12)
Authority: 312/312 (217/217 subset)
Binary patches: 26 (P1-P26), backup at ~/.claude/patch_backups/
PR #746: MERGED
Next: META-BRIDGE-BOUNDED-REVIEW-FIX
Reviewer override: Claude (temporary, until Friday)
```
