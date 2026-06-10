# Docs Sync Exempt Agent Memory 2026-06-09 2026-06-10

Date: 2026-06-10
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: docs-sync-exempt-agent-memory-2026-06-09
Phase-A-Lock: LOCKED
Purpose: GOAL: Stop the docs-governance sync check from flagging agent-written .claude/agent-memory/ markdown as "Unclassified", which makes docs_sync_report.py --check return exit 1 and block otherwise-clean commits (it blocked the packet-l4-autopopulate wave's commit when advisor memory existed under .claude/agent-memory/advisor/).

## Scope

Add a .claude/agent-memory/ exemption to docs_registry.json exempt_patterns (mirroring the existing .claude/ agent-surface exemptions) plus a regression test, so agent-memory markdown stops tripping docs_sync_report --check (exit 1) and blocking commits. Tooling-only L4_ENABLER; no runtime dirs.

- `reports/deferred/non_blocking/docs-sync-exempt-agent-memory-2026-06-09_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Request from Post-Merge Supervisor

GOAL: Stop the docs-governance sync check from flagging agent-written .claude/agent-memory/ markdown as "Unclassified", which makes docs_sync_report.py --check return exit 1 and block otherwise-clean commits (it blocked the packet-l4-autopopulate wave's commit when advisor memory existed under .claude/agent-memory/advisor/).

CONTEXT (verified by reading the code): tools/docs/docs_sync_report.py classifies every markdown file via classify_md_path (in tools/docs/shared_doc_config.py), driven by the exempt_patterns regex list in mu/tools/docs/docs_registry.json. A markdown path matching no registered/governed/exempt pattern is classified unknown and appended to unclassified_markdown; with --check, any unclassified file returns exit 1. The registry ALREADY exempts agent/scratch surfaces, including the .agent_bus tree, .claude/rules/, .claude/agents/, .claude/commands/, .claude/skills/, and .scratch/. The .claude/agent-memory/ subtree (agent/advisor memory markdown) is NOT exempt, so it trips the check.

REQUIRED FIX (narrow, single concern): add a regex anchored at .claude/agent-memory/ to the exempt_patterns list in mu/tools/docs/docs_registry.json, mirroring the existing .claude/rules/ agent-surface exemption. Add a regression test under mu/tests/docs/ asserting that a .claude/agent-memory/advisor/<name>.md path classifies as exempt (NOT unknown) via classify_md_path, and that docs_sync_report.collect_report() no longer lists agent-memory markdown under unclassified_markdown. Keep all existing exemptions and docs-governance behavior unchanged.

This is an L4_ENABLER tooling-only change: it MUST NOT touch any runtime dir (mu/host, mu/substrate, mu/closures, mu/bridge, mu/programs, rcx_pi/selfhost, mu/tools/compilers). No new heuristic, no masking (no retry/skip/xfail, do not weaken existing docs-governance tests), and do not broaden the exemption beyond the single .claude/agent-memory/ prefix.

Routed next-candidate:
docs-sync-exempt-agent-memory-2026-06-09

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/docs-sync-exempt-agent-memory-2026-06-09.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id docs-sync-exempt-agent-memory-2026-06-09 --output reports/l4_wave_indicators/docs-sync-exempt-agent-memory-2026-06-09.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_docs_registry_agent_memory_exempt.py mu/tests/docs/test_growth_caps.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/docs_sync_exempt_agent_memory_2026-06-09_2026-06-10.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: docs-sync-exempt-agent-memory-2026-06-09.
<!-- L4_FIELDS_FROM_TRACKER:end -->

## Work items

Concrete bounded tasks for Phase B (single concern; tooling-only):

1. Add one regex anchored at the `.claude/agent-memory/` prefix to the `exempt_patterns` list in `mu/tools/docs/docs_registry.json`, mirroring the existing `.claude/rules/` agent-surface exemption. Do not modify any other entry and do not change `classify_md_path` in `tools/docs/shared_doc_config.py`.
2. Add the regression test `mu/tests/docs/test_docs_registry_agent_memory_exempt.py` asserting:
   - a `.claude/agent-memory/advisor/<name>.md` path classifies as **exempt** (not `unknown`) via `classify_md_path`; and
   - `docs_sync_report.collect_report()` does not list agent-memory markdown under `unclassified_markdown`.

Current state per the tracker note `progress_proof_before`: `.claude/agent-memory/` markdown classifies as `unknown`, so neither item is yet landed; both remain pending Phase B.

## Constraints

What is NOT in scope:

- MUST NOT touch any runtime dir: `mu/host`, `mu/substrate`, `mu/closures`, `mu/bridge`, `mu/programs`, `rcx_pi/selfhost`, `mu/tools/compilers`. This is an `L4_ENABLER` tooling-only change.
- Do NOT broaden the exemption beyond the single `.claude/agent-memory/` prefix.
- Do NOT add a new classification heuristic or alter `classify_md_path` behavior for any other path.
- No masking: no retry/skip/xfail, and do not weaken or delete any existing docs-governance test.
- Keep all existing `exempt_patterns` entries and docs-governance behavior unchanged.

## Stop conditions

- STOP if the exemption cannot be expressed as a single `.claude/agent-memory/`-anchored regex without editing `classify_md_path` / `shared_doc_config.py` heuristics or touching a runtime dir — escalate instead of widening scope.
- STOP if the regression test cannot pass without masking (retry/skip/xfail) or without weakening an existing docs-governance test.
- STOP if any existing docs-governance test (the `docs_sync` / `doc_contracts` suite) regresses.
- STOP and request a founder decision (POLICY_BOUND) if doc-governance policy turns out to require `.claude/agent-memory/` to be governed rather than exempt.
- STOP at the Phase A → Phase B boundary: this packet does not implement the fix; Phase B owns the edit + test under the executor pipeline.

## Acceptance criteria

- `mu/tools/docs/docs_registry.json` `exempt_patterns` gains a single regex anchored at `.claude/agent-memory/`, mirroring the `.claude/rules/` exemption; every prior exemption is retained unchanged.
- `mu/tests/docs/test_docs_registry_agent_memory_exempt.py` exists and asserts both the classifier and `collect_report()` behaviors described in Work items.
- Evidence command passes: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/docs/test_docs_registry_agent_memory_exempt.py`.
- `progress_proof_after` holds: `.claude/agent-memory/` markdown classifies as exempt, so `docs_sync_report.py --check` no longer lists it and no longer returns exit 1 on that account.
- No runtime dir is touched; the pre-existing docs-governance suite still passes.
- Indicator artifact collected via: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id docs-sync-exempt-agent-memory-2026-06-09 --output reports/l4_wave_indicators/docs-sync-exempt-agent-memory-2026-06-09.json`.

## Grounding / Authorization

- Authorizing tracker note: `TASKS.md` — `Tracker sync note (2026-06-10, docs-sync-exempt-agent-memory-2026-06-09)`, `NEXT-CODEX-POST-REDTEAM`, Class `L4_ENABLER`, `target_gate_id: G8`.
- Governing packet: this file, `reports/control_plane/docs_sync_exempt_agent_memory_2026-06-09_2026-06-10.md` (the `Packet:` referenced by that tracker note).
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/docs/test_docs_registry_agent_memory_exempt.py` (matches the tracker note `evidence_command`).
- `FOUNDER_OVERRIDE:docs-sync-exempt-agent-memory-2026-06-09`
- Authorization: standing pipeline-bug-fix authorization (this is a control-plane docs-governance check that blocks otherwise-clean commits; per memory `feedback_autonomous_executor_fix.md`). The wave-bound `FOUNDER_OVERRIDE` token above matches the tracker note verbatim so commit automation derives the same-wave override mechanically.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `docs-sync-exempt-agent-memory-2026-06-09`
- Active packet: `reports/control_plane/docs_sync_exempt_agent_memory_2026-06-09_2026-06-10.md`
- Indicator artifact: `reports/l4_wave_indicators/docs-sync-exempt-agent-memory-2026-06-09.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/docs/test_docs_registry_agent_memory_exempt.py`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tools/docs/docs_registry.json`
  - `reports/control_plane/docs_sync_exempt_agent_memory_2026-06-09_2026-06-10.md`
  - `reports/deferred/non_blocking/docs-sync-exempt-agent-memory-2026-06-09_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/docs-sync-exempt-agent-memory-2026-06-09.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `docs-sync-exempt-agent-memory-2026-06-09`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/docs-sync-exempt-agent-memory-2026-06-09_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `docs-sync-exempt-agent-memory-2026-06-09`
- Active packet: `reports/control_plane/docs_sync_exempt_agent_memory_2026-06-09_2026-06-10.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `7bebcea868e8eec2c705175435771bf8d3801c021d4470fc83bdb596b49d92ae`
- Indicator artifact: `reports/l4_wave_indicators/docs-sync-exempt-agent-memory-2026-06-09.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_docs_registry_agent_memory_exempt.py mu/tests/docs/test_growth_caps.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/docs_sync_exempt_agent_memory_2026-06-09_2026-06-10.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/docs-sync-exempt-agent-memory-2026-06-09.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/docs/test_docs_registry_agent_memory_exempt.py`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tools/docs/docs_registry.json`
  - `reports/control_plane/docs_sync_exempt_agent_memory_2026-06-09_2026-06-10.md`
  - `reports/deferred/non_blocking/docs-sync-exempt-agent-memory-2026-06-09_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/docs-sync-exempt-agent-memory-2026-06-09.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
