---
DOC_STATUS: tracked_packet
wave_id: preflight-stale-check-retire-and-bridge-config-autoheal-2026-04-17
wave_class: L4_ENABLER
target_gate_id: G8
created: 2026-04-17
status: Phase A (plan under review)
---

# Preflight — Retire Stale Checks + Bridge-Config Auto-Heal

## Motivation

Three BLOCKING findings surfaced during wave `preflight-session-staleness-detection-2026-04-17` (merged as PR #779, commit `a29e1405` on 2026-04-17). Per founder directive 2026-04-11 + commit_executor critical-path guard at `commit_executor.py:1834-1837`, findings on `.claude/skills/preflight/` and `mu/tools/executors/` are ALWAYS blocking — not deferrable. This wave addresses all three.

## Finding 1 — P27 stale check in SKILL.md step 19

**Bug file:line:** `.claude/skills/preflight/SKILL.md:257`

**Current content:**
```
[ "$(grep -c 'proactive review' $F)" -eq 0 ] && echo "P27 MISSING" && N=$((N+1))
```

**Root cause:** P27 was the v2.1.104 anti-redteam patch that replaced CX4 text ("Don't add features, refactor code...") with text containing the phrase `proactive review`. In v2.1.112, Anthropic reworded the anti-redteam surface to `"adversarial probes is a happy-path confirmation, not verification. It will be rejected."` — verified in-binary 2026-04-17. Neither the original CX4 text nor the P27-era replacement exists in v2.1.112.

**Silent regression mechanism:** the check false-positives every session with `NEEDS_REPATCH=1` bumped from P27 MISSING. Operator habituates to "2 false positives are normal" (Finding 1 + Finding 2), masking any real NEEDS_REPATCH=3 signal.

**Fix:** delete `.claude/skills/preflight/SKILL.md:257`.

## Finding 2 — P_OjH check uses stale v2.1.104 function name

**Bug file:line:** `.claude/skills/preflight/SKILL.md:261`

**Current content:**
```
[ "$(grep -c 'function OjH(H){return!1' $F)" -eq 0 ] && echo "P_OjH MISSING (feature-flag gate not nullified)" && N=$((N+1))
```

**Root cause:** v2.1.112 renamed the A/B-gate function `OjH(H)` to `_Y8(H)`. Verified in-binary 2026-04-17: `grep -c 'function _Y8(H){return!1' binary` = 1 (patched correctly per `reference_tweakcc_repatch.md:519-522`); `grep -c 'function OjH(H){return!1' binary` = 0 (function renamed by Anthropic). The SKILL.md verifier still searches for the old function name.

**Silent regression mechanism:** same alert-fatigue path as Finding 1; in addition, this one masks a HIGH-SAFETY-VALUE patch (the feature-flag gate nullification that disables multiple anti-patterns at once per `reference_tweakcc_repatch.md:724`). A regression of the underlying P_OjH patch would hide under the known false positive.

**Fix:** at `.claude/skills/preflight/SKILL.md:261`, change `'function OjH(H){return!1'` → `'function _Y8(H){return!1'`.

## Finding 3 — `.agent_bus/bridge_config.json` absent in fresh worktrees

**Error site (leaf):** `mu/tools/agents/bridge_adapters.py:429-434`
```
def load_bridge_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        raise BridgeAdapterError(
            f"Bridge config not found at '{config_path}'. ..."
        )
```

**Propagation site:** `mu/tools/executors/commit_executor.py:1739-1750` — constructs `config_path = repo_root / ".agent_bus" / "bridge_config.json"`, calls `load_bridge_config()`, catches `BridgeAdapterError`, returns `bot_findings_pending` with message "Step 15: cannot load bridge adapter: {exc}".

**Root cause:** `.gitignore:113` excludes the entire `.agent_bus/` tree (intentional — config may contain local CLI paths/credentials). `git worktree add` only populates tracked files into a new worktree, so a fresh linked worktree contains NO `.agent_bus/` directory at all (empirically verified 2026-04-17 on `/private/tmp/workingrcx_preflight_stale_fixes_2026-04-17` immediately after `git worktree add`: `ls .agent_bus/` → "No such file or directory").

**Silent regression mechanism:** tier 3 bot-remediation on any fresh-worktree wave silently fails with `recovered=False`. This outcome is indistinguishable by log scanning from "adapter ran and found no fix." Operator must read the specific "cannot load bridge adapter" line to realize the adapter never started. Every fresh worktree is affected.

**Fix location:** insert self-heal block immediately after `mu/tools/executors/commit_executor.py:1739` (between path construction and `load_bridge_config()` call). Logic:
- If `config_path.exists()`: proceed unchanged.
- Else: locate main worktree via `git worktree list --porcelain` (first `worktree ` entry). If main's `.agent_bus/bridge_config.json` exists, copy it to `config_path` with log "Step 15: auto-copied bridge_config.json from {main_path}".
- If main also lacks the file: fall through to `load_bridge_config()` which raises as before (preserving fail-closed contract).

**Why at this location:** (a) fixing at the leaf `load_bridge_config` changes library semantics for all callers, unwanted; (b) fixing at `.gitignore` risks committing local credentials; (c) fixing at the caller site keeps the loader's fail-closed contract and adds self-heal only where needed.

## Scope

- `.claude/skills/preflight/SKILL.md` — 2 edits (delete line 257, rename string at line 261).
- `mu/tools/executors/commit_executor.py` — 1 insertion (~15 lines of self-heal block) immediately after line 1739.
- `reports/control_plane/preflight_stale_check_retire_and_bridge_config_autoheal_2026-04-17.md` — this packet.

## Non-Scope

- Structural refactor of SKILL.md step 19 to auto-derive check strings from `reference_tweakcc_repatch.md`. That would prevent all future text-drift bugs of the Finding 1/2 class but requires a separate design wave.
- Ungitignoring `.agent_bus/` or tracking the bridge config template in a non-gitignored location. Founder direction required for credential-handling decisions.
- Updating `reference_tweakcc_repatch.md` to retire P27 from the active patch list. That's memory-only (not a repo commit) and can be done in a follow-up memory-hygiene step.

## Evidence Plan

- **Fix 1+2 evidence:** extract the updated step 19 bash block from SKILL.md and run against current v2.1.112 binary → `NEEDS_REPATCH=0` (was 2 before, from P27 MISSING + P_OjH MISSING false positives).
- **Fix 3 evidence:** in a simulated fresh-worktree scenario (remove `.agent_bus/bridge_config.json` from a test directory), invoke the commit_executor auto-heal path and verify:
  - `config_path` exists after self-heal.
  - Log line "auto-copied bridge_config.json from {main_path}" emitted.
  - `load_bridge_config()` succeeds on the copied file.

## Phase-A-Lock

Locked to the three files listed in Scope. No implementer may touch files outside this list.

## Tracker Note

Auto-generated via `build_commit_handoff()` with FOUNDER_OVERRIDE appended. Wave class L4_ENABLER, target gate G8, non-structural adjacency bypass authorized by founder this session.
