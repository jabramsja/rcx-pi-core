# Phase 3A Control-Surface Blockers

**Date:** 2026-03-20
**Lane:** hooks / agents / bridge control-surface red-team
**Status:** RESOLVED (2026-03-29, deferred_cleanup wave)
**Source queue:** `reports/codex/repo_audits/drift_2026-03-20_codex_redteam_phase_queue.md`

---

## Context

These blockers were reproduced during the founder-directed `TASKS.md` `NOW`
control-surface lane review and were not yet captured in the active deferred
blocking/non-blocking inventory as founder-facing truth.

The non-blocking residue packet
`reports/deferred/non_blocking/hook_soft_gate_residue.md` already carries the
per-agent verdict-validation scope-expansion item. This blocker packet covers
the remaining live bypass, the proof-class gap around current closeout claims,
and the untracked plugin-capability governance gap.

---

## B1. Missing `agent_type` Silently Bypasses the Compliance Hook

**Class:** DEFECT
**Files:** `.claude/hooks/validate-agent-compliance.sh:27-42`
**Status:** FIXED (PR #682, 2026-03-23)

**What was wrong**

The hook claimed fail-closed security, but missing or unknown `agent_type`
fell through the `case` dispatch and exited `0` without emitting block JSON.

**Direct evidence**

- Source:
  - `AGENT_TYPE=$(echo "$INPUT" | jq -r '.agent_type // empty' | tr '[:upper:]' '[:lower:]')`
  - `case "$AGENT_TYPE" in ... *) exit 0 ;; esac`
- Runtime repro:
  - `printf '{"agent_transcript_path":"/nonexistent"}\n' | ./.claude/hooks/validate-agent-compliance.sh`
  - Result: empty stdout, exit code `0`

**Resolution proof:** Hook now emits `{"decision":"block","reason":"Unknown agent_type: ..."}` for missing/unknown agent_type. Regression tests: `TestHookExecutionAgainstMalformedPayloads` (4 tests) in `test_validate_agent_compliance.py`.

---

## B2. Current Closeout/Residue Wording Overstates Proof Class

**Class:** DOC_ACCURACY
**Files:**
- `reports/deferred/non_blocking/hook_soft_gate_residue.md:87-153`
- `tests/tools/test_validate_agent_compliance.py:762-831`
- `tests/tools/test_agent_tooling_smoke.py:209-225`
**Status:** FIXED (deferred_cleanup wave, 2026-03-29)

**What is wrong**

The active residue packet reads as if the validator/hook hardening slice is
substantially closed, but the proof only covers part of the claim surface.

**Direct evidence**

- The residue packet marks item 8 as PARTIALLY RESOLVED while also recording:
  - `printf '### CHECKED\n- x\n### NOT_CHECKED\n- y\nVERDICT: ROBUST\n' | ... --strict` → `compliant: true`
- Hook integration tests in `tests/tools/test_validate_agent_compliance.py`
  only inspect source text for hook behavior; they do not execute the hook
  against missing-`agent_type` payloads.
- Strict-mode smoke coverage in
  `tests/tools/test_agent_tooling_smoke.py:209-225` checks only weak approval
  structure, not cross-agent verdict misuse or live hook bypasses.
- Repo search found no targeted regression coverage for:
  - `agent_type`
  - `agent_transcript_path`
  - `ROBUST`
  - `BANANA`
  - `nonexistent`
  in the validator/hook test files.

**Resolution proof:** 4 hook execution tests added (`TestHookExecutionAgainstMalformedPayloads`) that run the actual shell script with crafted JSON inputs: missing agent_type, unknown agent_type, empty payload, valid agent_type.

---

## B3. Telegram Plugin Enablement Lacks Active Governance Grounding

**Class:** POLICY_BOUND
**Files:** `.claude/settings.json:52-54`
**Status:** STALE (telegram plugin not present in current settings.json)

**What is wrong**

The control surface now enables `telegram@claude-plugins-official`, but the
active tracker/deferred surfaces do not explain why this capability was enabled
or what governance/risk posture applies to it.

**Direct evidence**

- Source:
  - `"enabledPlugins": { "telegram@claude-plugins-official": true }`
- Repo search in active tracker/deferred surfaces found no corresponding
  founder-facing grounding entry beyond the settings file itself.

**Resolution:** Plugin no longer present in `.claude/settings.json`. Item is stale — no governance action needed.

---

## Relationship To Existing Deferred Items

- `reports/deferred/non_blocking/hook_soft_gate_residue.md` item 12 already
  tracks per-agent verdict validation as non-blocking scope expansion.
- This blocker packet does **not** duplicate that item.
- The blocker here is the still-live missing-`agent_type` bypass plus the fact
  that current report wording/proof class is stronger than the reproduced state.
