<!--
DOC_STATUS
TYPE: REFERENCE
LAST_VERIFIED: 2026-02-09
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: tests/docs/test_doc_contracts.py

This header enables automated doc drift detection.
- REFERENCE: Stable definitions, rarely changes
- DESIGN_SPEC: Architectural intent, may diverge from implementation
- IMPLEMENTATION: Active development, should match current code

If this doc's claims don't match reality, update the doc or fix the code.
Run: pytest tests/docs/test_doc_contracts.py -v
-->

# Agent Runbook v0

Purpose: practical instructions for running RCX agents via SDK runners.

**Quick Reference:** `./tools/agents.sh`

## Current Codex Pipeline Contract

For Codex-operated WorkingRCX waves, `run_review.py` is not the active
pre-merge review path. The current executor config sets
`agent_review_enabled=false`, so Phase A and Phase B skip SDK agent review and
route review through the dispatcher/bridge/pre-commit/commit-executor pipeline.

Current Codex path:

```bash
python3 mu/tools/executors/executor_dispatch.py --routing-record .agent_bus/meta/post_merge_routing.json --json
```

Use `run_review.py` only when a separate Claude/SDK review wave explicitly
requires it and the SDK runner is available. Do not substitute `run_review.py`
for dispatcher, Phase B, pre-commit supervisor, or commit executor in Codex
sessions.

### Operator Orchestrator Mode vs Pipeline Roles

The active main-session orchestrator is selected separately from the pipeline
implementer/reviewer roles.

Use the orchestrator switch when changing which main session owns pager wakeups,
tmux monitor refresh, and autoping:

```bash
python3 mu/tools/session/set_orchestrator_mode.py --mode codex --repo-root "$PWD" --bus-dir .agent_bus --tmux-session rcx-pipeline --apply
python3 mu/tools/session/set_orchestrator_mode.py --mode claude --repo-root "$PWD" --bus-dir .agent_bus --tmux-session rcx-pipeline --apply
python3 mu/tools/session/set_orchestrator_mode.py --mode codex --repo-root "$PWD" --bus-dir .agent_bus --tmux-session rcx-pipeline --verify
```

The switch writes bus-local `orchestrator_mode.json`, which the pager uses as
the effective route ahead of the shipped `executor_config.json` default. It
terminally skips stale pending pager targets for the opposite orchestrator, stops
the opposite autoping surface, starts the selected Codex or Claude autoping
surface, and rebuilds the selected tmux monitor. Dry-run/show mode reports the
exact changes and commands without writing files or starting processes.

Use the role switch only when changing who implements or reviews pipeline work:

```bash
python3 mu/tools/executors/set_roles.py --implementer codex --reviewer claude
python3 mu/tools/executors/set_roles.py --implementer claude --reviewer codex
```

`set_roles.py` writes `role_agents` plus derived `backends` and
`bridge_reviewers`; it does not change orchestrator mode, effective pager route,
tmux, or autoping state. `set_orchestrator_mode.py` writes the bus-local
orchestrator state and narrows the tracked pager fallback for the selected
orchestrator; it does not write `role_agents`, `backends`, or
`bridge_reviewers`.

Provider display/model/effort metadata for Codex and Claude lives in one
registry: `mu/tools/executors/executor_config.json` under
`bridge_agent_defaults`. Update that JSON registry when model names, effort
levels, or display labels change so launcher output, tmux labels, and
orchestrator verification stay aligned.

## Tool Overview

### Native validation execution and budget transport

`validation_execution.py` is the shared child-execution policy used by the
existing Phase B and commit callers. It does not dispatch or retry waves.
Phase B uses the full pytest profile; commit uses `ci_fast`, importlib import
mode and `not slow and not fuzzer`. Both preserve explicit test selections,
pin deterministic hashing, run every selected test despite inherited exitfirst,
and disable automatic worker restart. Parallel execution uses at most four
xdist workers with work stealing. Explicit serial execution omits xdist flags;
unavailable/disabled xdist or incompatible inherited options refuse admission.
Zero collection and pytest errors cannot become a successful gate. Two existing
gate contracts remain: an empty selection starts no process, and a commit
selection whose collected tests the fast profile deselects entirely passes
with pytest's exit 5. xdist reports that case as zero items, so one serial
collection-only child (same selectors, configuration, import mode and
environment, minus only the profile marker) must collect real items within the
remaining leaf allowance. Its uncertainty or refused admission is a HOLD; zero
collection, collection errors and its timeout still fail. The shared runner
itself refuses an empty selector list.

Each child retains its actual argv, profile, finite allowance, timestamps, exit
status and complete stdout/stderr in the active bus validation directory (or
the explicitly selected validation-log directory). The child writes kernel
pipes that only the runner copies into those files, so recorded output hashes
are final. A validation completes only when its leader has exited and both
streams have reached end-of-file, within the same finite allowance. End-of-file
proves that every holder of a stream, including a reparented descendant, has
closed it. That is the bounded completion the earlier captured-pipe callers had.
A writer still holding either stream at that boundary is an ownership HOLD
(`output_complete` false, `unresolved_output_streams` named). It is never
success, so evidence restoration and further admission stop while it can still
write. Progress reports start, bounded running updates (including a leader that
has exited while its output is still open) and finish. Timeout/interruption uses
the existing identity-checked ownership helper and then drains boundedly;
uncertainty holds further execution and preserves diagnostics. Normal exit is
not whole-tree release evidence, and stream end-of-file is not process release.
An unavailable pipe or copier primitive HOLDs before the child is admitted. A
failed durable write or close is an execution error, never success; draining
continues so writer closure stays observable.

Optional `validation_schedule` requests are admitted by the native launcher
against current source/config, exact evidence command and wave/bus identity.
They preserve existing scalar defaults and per-key meanings; no global timeout
is increased. Every leaf remains within the existing 7200-second ceiling.
Enclosing allocations account for existing implementation/review/delivery and
contained validation/CI allowances. A request smaller than the ordinary
supervisor validation leaf is rejected before expensive execution. The immutable
transport is carried through routing and commit handoff. The launch-owned
admission ledger and immutable stage witness retain the original clocks across
fresh processes; missing, expired, conflicting or reset authority HOLD. Recovery
cannot replace that budget with a scalar timeout override.
Contended first-admission locks also HOLD immediately, before any clock or
budget record is created; admission never waits indefinitely for another consumer.

At supervisor handoff, current source bootstraps the narrow dependency refresh
even when both the previous common module and client callable remain cached.
The client handoff executes both dependencies from bound bytes every time. A
newly imported supervisor runs the same transaction but keeps a registered
dependency only when its execution is proven: each module records the module
code object its own import actually ran (`EXECUTED_MODULE_CODE`), and that
object must equal the code the bound source bytes compile to. Symbol
compatibility never proves which code ran. A proven pair is kept, so modules
imported earlier keep their class and exception identity, and a missing
`validation_execution` is executed against the proven common module. A stale
but symbol-compatible owner (one loaded from an accepted same-size/same-time
timestamp cache, for example), a module without that witness, or an absent,
incompatible or incoherent pair is executed again as a whole; a foreign source
still refuses. Both `executor_common` and `validation_execution` are compiled from
the exact source bytes read for each warm, cold or absent-module handoff, with
the import system's compile semantics (no inherited `__future__` flags). Validation uses
that executed common module; timestamp/size bytecode and either module's
self-reported disk hash cannot establish execution provenance, even under `-B`.
Both cached source paths are checked before either replacement is published.
Compile/import failure, interruption, missing guard capability or drift in either
source restores both prior module entries, including absence, and refuses the
handoff. No admission identity, retained clock or finite ceiling is reset. Existing
executor callables keep their original modules and review/routing guards remain
in place. After private-review GO, a changed, already-owned active nonblocking
report can receive a separate deterministic transition seal. Its original
prepared source/index and canonical reviewer envelope remain retained. One
fresh continuation can run the remaining gates after final-gate failure; replay,
unexplained source/index drift, substituted review output or interrupted
consumption HOLD. Archive/deletion report transitions require separate authority.

The phase sequence stays design review → implementation → independent convergence
→ final native validation → pre-commit supervision → staged candidate checks
→ commit hooks → push checks → exact-head hosted CI → required bot/human review
→ merge → PRIMARY sync → verified cleanup. Local performance measurements and
local passing tests do not replace any phase or grant delivery/release authority.

Hybrid recovery uses that same runner and the full pytest profile for every
retained selector, with at most four workers and no exitfirst truncation. The
existing 300-second ordinary leaf and exact full-fleet allowances remain;
sequential validators share one source/command/config-bound enclosing budget,
limited to 7200 seconds. Admission checks the total allocation and the existing
parent's remaining sequential reserve before expensive work. Each child consumes
that original enclosing clock; a later leaf cannot restart it or consume the
next leaf's reserve. Worker absence, invalid authority and ownership uncertainty
produce structured HOLD through validation, recovery-loop and caller boundaries.
Ordinary assertion failures keep their failure behavior and latest diagnostics.

A supervisor `VALIDATION_BUDGET_HOLD` retains its structured error code, detail
and validation evidence through commit rejection and all three Phase B
supervisor boundaries (initial, post-reentry and commit-ready status refresh).
Phase B preserves the existing checkpoint bytes even if HOLD notification
fails. Caller CLIs exit nonzero and recovery classifies the result as terminal
policy without admitting a corrective actor, review or commit. Ordinary
assertion errors and `NEEDS_PHASE_B` retain their existing routing; mentioning
HOLD in diagnostic text does not create terminal authority.

The recovery validator retains outer streams, JUnit identities, selected targets,
budgets and receipts in an external validation-log directory, separate from the
candidate. Its test children receive that contained evidence path and temporary
execution/cache roots. Live bus, role, pager and stage-authority environment keys
are isolated only for tests; ownership chains, unrelated keys and deterministic
pins remain. The parent environment is unchanged. Timeout/interruption retains
available output; uncertain writers retain scratch and provider guards. The final
native scope audit and immutable Git-control checks still run, with no generated
output exemption. These checks do not resolve unsampled Darwin lifetime
attribution or manufacture whole-tree release evidence.

### Declared review reports and corrective implementation

Phase B reads exact blocking and nonblocking report destinations from the
existing candidate-authority spec and verifies its launch-bound identity before
each ordinary, re-entry and private-attribute remediation review. The task sent
to the reviewer includes those destinations. This contract covers the entire
review, including any rechecks and files written after an envelope. A declared
directory is not permission to invent a report suffix or use a directory glob.
The frozen report slots are exactly the wave's candidate-allowlist entries named
`<wave_id>_*.md` directly under `reports/deferred/blocking/` and
`reports/deferred/non_blocking/`. A wave may declare no blocking slot. The
pre-commit supervisor package lists every non-README Markdown file under
`reports/deferred/blocking/` as a blocker, and supervisor Gate 7 fails any that
is not acknowledged. Such a wave therefore keeps blocking findings in the
reviewer envelope, its packet and its implementation evidence, never in a new
blocking-lane file.

Immediately after the reviewer finishes, Phase B checks the actual worktree and
index against the same authority, before consuming continuation or invoking a
corrective implementer. Candidate source bytes/modes, index entries/flags, HEAD,
branch, effective configuration and inherited owner must remain unchanged;
declared findings reports cannot be deleted or redirected through symlinks.
The exact task text, including this report contract, is used for durable reviewer
ownership checks without rewriting the original prepared checkpoint.
Undeclared output is retained and produces a structured
scope failure with the original decision and diagnostics. Valid declared report
outputs join the next correction's sealed file inventory; no live allowlist or
old checkpoint is expanded or resealed. `REQUEST_CHANGES` and `NO_GO` remain
blocking and require correction followed by fresh review. If a required report
cannot be written to an allowed destination, return the existing structured
blocking outcome with findings in the reviewer envelope. Do not invent another
repository path or downgrade findings. Later authoritative guards remain active.
Optional legacy invocations without candidate authority keep their existing
behavior; an optional authority spec, when present, is still enforced and must
remain identical across the review. Symlinked report destinations refuse.

Two complementary systems exist for running agents:

### 1. Native Subagents (`.claude/agents/`) — Ad-Hoc Use

9 native Claude Code subagents for quick, targeted, interactive checks during development. No SDK or Python orchestration needed.

| Feature | Detail |
|---------|--------|
| **Location** | `.claude/agents/*.md` |
| **Source of truth** | `tools/agents/*_prompt.md` (sync via `bash tools/sync_native_agents.sh`) |
| **How to invoke** | `Agent(name="adversary", prompt="Review <file> for <focus>")` in any Claude Code session |
| **Permission mode** | `plan` (read-only — agents can Read/Grep/Glob but cannot write files) |
| **Memory** | `project` scope — agents remember findings across sessions |
| **Contract** | Red-team contract from `tools/agents/_contract_redteam.md` is inlined into each agent file |
| **Compliance** | `SubagentStop` hook in `.claude/settings.json` validates agent output format |

**Available agents:** `adversary`, `verifier`, `expert`, `structural-proof`, `grounding`, `fuzzer`, `translator`, `visualizer`, `advisor`

**When to use:** Quick single-agent checks during development, targeted review of specific files/functions, ad-hoc security or invariant verification.

**When NOT to use:** Current Codex pipeline waves (use dispatcher / Phase B /
pre-commit supervisor / commit executor), or any explicit SDK batch review that
requires parallel groups, depth tiers, unified reports, or verdict synthesis.

### 2. SDK Orchestrator (`run_review.py`) — Legacy Claude/SDK Batch Review

Parallel SDK review with depth tiers, unified reports, and regression tracking.
This is not the current Codex pre-merge gate while
`mu/tools/executors/executor_config.json` has `agent_review_enabled=false`.

| Tool | What it is | When to use | Time |
|------|------------|-------------|------|
| `run_review.py` | Multi-agent code review orchestrator | Explicit Claude/SDK review wave | ~8-30 min (scope/model dependent) |
| `run_deep_analysis.py` | Full codebase health scan | Monthly, pre-release, or after large refactors | ~5-10 min |
| `run_ci_review.py` | Lightweight CI review | Manual dispatch in GitHub Actions (API cost) | ~2-4 min |
| `run_interactive.py` | Conversational agent session | When you want to dig deeper with follow-up questions | Interactive |
| `bridge_supervisor.py` | Claude ↔ Codex collaboration bridge | After implementation, for independent Codex review; design deliberation | ~3-10 min |

**Decision guide:**
- Quick check on one file? → Native subagent (`Agent(name="adversary", prompt="...")`)
- Codex wave ready? → `executor_dispatch.py` / Phase B / pre-commit supervisor / commit executor
- Explicit Claude/SDK review requested and available? → `run_review.py`
- Monthly health check? → `run_deep_analysis.py`
- Want to explore a finding? → `run_interactive.py <agent> <files>`
- Implementation ready for independent review? → `bridge_supervisor.py review`
- Design proposal or question for dialectic? → `bridge_supervisor.py review --no-diff`

## Recommended Workflow Tiers

| Tier | Command | When | Time |
|------|---------|------|------|
| **Codex Pipeline** | `python3 mu/tools/executors/executor_dispatch.py --routing-record .agent_bus/meta/post_merge_routing.json --json` | Current Codex waves | varies |
| **SDK Quick** | `python tools/runners/run_review.py --pr --depth quick` | Explicit Claude/SDK review only | ~2-3 min |
| **SDK Full** | `python tools/runners/run_review.py --pr --depth full` | Explicit Claude/SDK review only | ~5-8 min |
| **SDK Rigorous** | `python tools/runners/run_review.py --pr --rigorous` | Explicit Claude/SDK review only | ~10-15 min |
| **SDK Release** | `python tools/runners/run_review.py rcx_pi/selfhost/ mu/ --rigorous --output reports/release_review.md` | Explicit release/hardening SDK review | ~15-20 min |

Times assume healthy SDK/runtime infrastructure (auth, Claude SDK, Bun compatibility). Infra failures can fail fast before review starts.

**SDK practical rules, when an explicit SDK review wave is active:**
1. Use `quick` for iteration, then `full` once before merge
2. Reserve `--rigorous` for high-risk PRs (`rcx_pi/selfhost/`, `mu/`, compliance/gating tooling)
3. If runtime is too long, reduce scope (files) before increasing depth
4. `--show-warnings` on `full` when you want detail on soft-gate findings

## Quick Start

```bash
# Current Codex wave path
python3 mu/tools/executors/executor_dispatch.py --routing-record .agent_bus/meta/post_merge_routing.json --json

# Legacy SDK review only when explicitly requested and available
python tools/runners/run_review.py rcx_pi/selfhost/ --depth full

# Legacy SDK PR review (auto-selects depth from diff)
python tools/runners/run_review.py --pr

# Interactive session with follow-up
python tools/runners/run_interactive.py adversary rcx_pi/selfhost/step_mu.py
```

## What is run_review.py?

`run_review.py` is the legacy SDK batch-review orchestrator. It is not the
current Codex pipeline entrypoint when SDK agent review is disabled in executor
config.

**What it does:**
1. Runs multiple specialized agents **in parallel** (3-4x faster than sequential)
2. Each agent checks a different aspect of your code changes
3. Synthesizes all findings into a unified report
4. Stores findings in memory for regression tracking
5. "Hard gate" agents (verifier, adversary, structural-proof) can block merge if they fail

**Depth levels control how many agents run:**
- `--depth quick` - 4 core agents (fast feedback)
- `--depth full` - 5-6 agents (`fuzzer` always, `grounding` risk-triggered)
- `--founder` - 7-8 agents (+ translator, visualizer for founder review)
- `--depth all` - 8-9 agents (+ advisor)

**Key parameters:**
- `--rigorous` - Validates reasoning quality, challenges approvals with skeptic agent
- `--pr` - Auto-detects changed files from git diff
- `--no-memory` - Disable finding storage
- `--show-warnings` - Show full warning details
- `--force-grounding` - Include grounding even for low-risk scopes
- `--fail-fast-hard-gate` - Stop after phase-1 hard gate failures
- `--skip-preflight` - Bypass mandatory runtime preflight (debugging only)
- `--preflight-timeout` - Preflight timeout in seconds
- `--model` - Override model for all orchestrated agents (`opus`, `sonnet`, `haiku`)

**Model governance:**
- Canonical defaults live in `tools/runners/shared_agent_utils.py` (`AGENT_DEFAULT_MODELS`)
- `run_review.py`, `run_ci_review.py`, `run_interactive.py`, `run_deep_analysis.py`, and direct runners all resolve model from that shared policy
- Preflight fails closed if SDK cannot honor explicit `model=...` wiring

**Architecture:** See `mu/docs/agents/AgentRig.v0.md` for trust model.

## Orchestrators

| Command | Purpose | Agents |
|---------|---------|--------|
| `run_review.py --depth quick` | Fast review | 4: verifier, adversary, expert, structural-proof |
| `run_review.py --depth full` | Full review | 5-6: + fuzzer always, grounding risk-triggered |
| `run_review.py --founder` | Founder review | 7-8: + translator, visualizer |
| `run_review.py --depth all` | Complete | 8-9: + advisor |
| `run_ci_review.py` | CI/CD | Auto-selects based on diff risk |
| `run_interactive.py` | Conversational | Single agent with follow-up |
| `run_deep_analysis.py` | Full-stack codebase health | 5: verifier, adversary, grounding, structural-proof, advisor |

## Individual Runners

All 9 agents have dedicated SDK runners with built-in compliance validation:

```bash
python tools/runners/run_verifier.py <files> [--model opus|sonnet|haiku]           # North Star compliance
python tools/runners/run_adversary.py <files> [--model opus|sonnet|haiku]          # Security/attack vectors
python tools/runners/run_expert.py <files> [--model opus|sonnet|haiku]             # Complexity review
python tools/runners/run_structural_proof.py "claim" [--model opus|sonnet|haiku]   # Verify structural claims
python tools/runners/run_grounding.py <files> [--model opus|sonnet|haiku]          # Test coverage
python tools/runners/run_fuzzer.py <files> [--model opus|sonnet|haiku]             # Property-based testing
python tools/runners/run_translator.py <files> [--model opus|sonnet|haiku]         # Plain English
python tools/runners/run_visualizer.py <files> [--model opus|sonnet|haiku]         # Mermaid diagrams
python tools/runners/run_advisor.py "problem" [--model opus|sonnet|haiku]          # Strategic advice
```

## Trigger Map (Which Agents to Run)

| Change Type | Recommended Depth |
|-------------|-------------------|
| Core logic (`rcx_pi/selfhost/`, `mu/`) | `--depth full` or `--founder` |
| Seed change (`mu/**/*.json`) | `--depth full` |
| Doc-only (`docs/`) | `--depth quick` |
| CI/tooling (`tools/`, `.github/`) | `--depth quick` |

## Compliance Validation

**All runners enforce `AgentGuardrails.v0.md`:**
- Every finding requires `FILE:LINE` + code snippet
- Fabrications are detected and blocked (code verified against actual files)
- Exit code 3 = compliance failure

**Validation is automatic** - built into every runner via `validate_agent_compliance.py --strict`.

**Prompt contract is centralized** - all runners inject `tools/agents/_contract_redteam.md`
via `load_agent_prompt_with_contract()` before agent-specific lens prompts.

## Rigorous Mode

For high-stakes changes, add `--rigorous` to challenge approvals:

```bash
python tools/runners/run_review.py rcx_pi/selfhost/ --rigorous
```

**What it does:**
1. **Reasoning validation** (`validate_agent_reasoning.py`) - CHECKED/NOT_CHECKED sections required for approvals
2. **Consolidated skeptic** (`run_skeptic.py`) - Single skeptic session reviews ALL approved agents at once, with per-agent verdicts and global blind spot detection
3. Skeptic can OVERRIDE individual approvals or flag GLOBAL_BLIND_SPOT concerns that affect all agents. Non-compliant or UNKNOWN skeptic output triggers fail-closed blocking.

**Use for:** Security-sensitive code, major refactors, pre-release audits.

**Skeptic verdicts:**
- `CONFIRMED` - Approval stands, proceed with merge
- `CONCERNS` - Issues found, should address before merge
- `OVERRIDE` - Approval rejected, do not merge

## Decision Rules (Gates)

| Agent | Gate Type | Blocks Merge If |
|-------|-----------|-----------------|
| verifier | Hard | REQUEST_CHANGES or NEEDS_DISCUSSION |
| adversary | Hard | VULNERABLE/NEEDS_HARDENING **with compliant machine-checkable proof** (`FILE`, `LINES`, `CODE`, `CALL_PATH`, `REPRO_STEPS`) |
| structural-proof | Hard | UNPROVEN or IMPOSSIBLE_AS_CLAIMED |
| expert | Soft | OVER_ENGINEERED (review recommended) |
| grounding | Soft | UNGROUNDED or THEATER (must fix before release) |
| fuzzer | Soft | BROKEN (must fix before release) |
| translator | Soft | DEVIATES (founder review) |
| visualizer | Soft | Red flags detected |
| advisor | None | Advisory only |

Runtime source of truth: `tools/runners/shared_agent_utils.py` (`HARD_GATE_AGENTS`).

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Pass |
| 1 | Fail (hard gate) |
| 2 | Warnings (soft gate) |
| 3 | Compliance failure |
| 4 | Infrastructure preflight failure |

## Interactive Mode

```bash
# Start session
python tools/runners/run_interactive.py verifier rcx_pi/selfhost/

# Commands during session
/switch adversary    # Switch agent (keeps context)
/files               # Show files in scope
/add <file>          # Add file
/save                # Save session
/exit                # End session

# Resume later
python tools/runners/run_interactive.py --list
python tools/runners/run_interactive.py --resume <session_id>
```

## Deep Analysis (Full-Stack)

For comprehensive codebase health analysis (monthly or before major releases):

```bash
python tools/runners/run_deep_analysis.py                    # All 5 agents
python tools/runners/run_deep_analysis.py --agents verifier,adversary  # Subset
python tools/runners/run_deep_analysis.py --verbose          # Show full output
```

**What it does:** Sends the full codebase (docs, tests, core code) to agents for DYNAMIC
analysis - finding issues that static tests miss:
- North Star drift (verifier)
- Cross-component security (adversary)
- Ungrounded claims (grounding)
- L1/L2/L3 validity (structural-proof)
- Strategic recommendations (advisor)

**When to run:** Monthly, before major releases, or after large refactors. NOT for every push.

## Bridge Supervisor (Claude ↔ Codex)

For independent Codex review of implementation work or design deliberation:

```bash
# Hybrid review: Claude implements, Codex reviews independently
python3 tools/agents/bridge_supervisor.py review \
  --task "implement X" --summary "added X to Y" --reviewer codex -v

# Design deliberation: no diff, Codex reviews proposal content
python3 tools/agents/bridge_supervisor.py review \
  --task-file proposal.md --summary "design review" \
  --reviewer codex -v --no-diff

# Full submit + run cycle (non-hybrid)
python3 tools/agents/bridge_supervisor.py submit --task-file task.txt --reader claude --reviewer codex
python3 tools/agents/bridge_supervisor.py run <job_id> -v --pause-after-reader
python3 tools/agents/bridge_supervisor.py continue <job_id> -v
```

**Canonical spec:** `mu/docs/agents/AgentBridgeProtocol.v0.md`

**Entrypoint:** `AGENT_BRIDGE.md`

## CI Integration

**GitHub Actions workflow:** `.github/workflows/agent-review.yml`

```bash
# Manual trigger via workflow_dispatch (always available)
python tools/runners/run_ci_review.py --pr-number 123 --post-comment

# NOTE: PR auto-trigger is DISABLED — agent review uses Anthropic API
# (pay-per-token), not the Max subscription. Use manual dispatch when
# API cost is justified, or run locally with:
#   python tools/runners/run_review.py <files> --depth quick
```

**Where outputs are stored (always):**
- PR comment: concise summary with per-agent snippets (`review-report.md` content)
- Actions artifact `agent-review-report` includes:
- `review-report.md` (concise, comment-friendly)
- `review-report-full.md` (expanded agent outputs, capped per agent)
- `review-results.json` (structured results + truncation metadata)

**How to find artifacts (new session safe):**
1. Open GitHub Actions run for the PR
2. Scroll to `Artifacts`
3. Download `agent-review-report`
4. Open `review-report-full.md` or `review-results.json` for full details

**Size control (prevents runaway files):**
- PR/comment snippets are capped via `--comment-snippet-chars` (default `1000`)
- Artifact outputs are capped via `--artifact-max-chars` (default `50000` per agent)
- If capped, a truncation marker is included in `.md` and `output_truncated=true` in `.json`

**Execution guardrails in workflow:**
- Skips automatically on fork PRs (secrets unavailable)
- Skips automatically when `ANTHROPIC_API_KEY` is missing
- Uses concurrency cancellation to avoid duplicate runs on rapid pushes

**Note:** CI review is a **fast signal**, not a full gate:
- Uses simplified verdict extraction
- Does NOT run reasoning validator or skeptic challenge
- Compliance validation is still strict (FILE:LINE must exist)
- Hard-gate failures (`verifier`, `adversary`, `structural-proof`) block CI; soft-gate findings are warnings
- For explicit SDK review depth, use `run_review.py --rigorous` locally

## Preflight

Before running SDK agents:
```bash
PYTHONHASHSEED=0 python3 tools/checks/check_agent_runtime.py
PYTHONHASHSEED=0 ./tools/audit_fast.sh
```

`run_review.py` also enforces SDK preflight automatically unless `--skip-preflight` is set.

## Agent Memory

Findings are automatically stored for regression tracking.

**Note:** Only `run_review.py` (orchestrator) updates agent memory. Individual runners
(`run_verifier.py`, etc.) do NOT update memory. Use the orchestrator for tracked reviews.

```bash
# View recent findings
python tools/runners/agent_memory.py list

# View findings for a file
python tools/runners/agent_memory.py list --file step_mu.py

# Check for regressions
python tools/runners/agent_memory.py check-regressions

# Mark finding as fixed
python tools/runners/agent_memory.py fix 42

# Clear old findings
python tools/runners/agent_memory.py clear --days 30
```

**Memory is enabled by default.** The orchestrator:
- Stores each FINDING from agent output with file:line and severity
- Warns when reviewing files with previously-fixed issues
- Associates findings with PR numbers (`--pr-number 123`)

Disable with `--no-memory` if needed.

## Syncing Native Agents

Native subagent files in `.claude/agents/` are generated from the source-of-truth prompt files in `tools/agents/`. If you update a prompt, re-sync:

```bash
bash tools/sync_native_agents.sh
```

This script:
1. Reads each `tools/agents/*_prompt.md` (YAML frontmatter + lens body)
2. Reads `tools/agents/_contract_redteam.md` (shared red-team contract)
3. Generates `.claude/agents/<name>.md` with contract inlined + native YAML fields (permissionMode, maxTurns, memory)

**Do NOT edit `.claude/agents/*.md` directly** — edits will be overwritten by the sync script. Edit `tools/agents/*_prompt.md` instead.

## Bridge Escalation

When `run_review.py` discovers CRITICAL or HIGH severity findings, you can automatically send them to the bridge for a Codex second opinion:

```bash
python tools/runners/run_review.py --pr --bridge-escalate
```

This is **advisory only** — it doesn't change the exit code or block merges. The bridge call is synchronous (up to 300s timeout), so the `run_review.py` process waits for the bridge to finish before exiting. The bridge invocation runs `bridge_supervisor.py review --no-diff` (deliberation mode) with a summary of the high-severity findings including file paths, extracted via `extract_findings_from_output()`.

**Note:** `--no-diff` routes the bridge reviewer into design-deliberation mode, which means the reviewer reasons about finding validity from the summary text alone — it does not independently verify findings against the live codebase. This is a deliberate tradeoff: a full code-review escalation would require a dedicated bridge review mode (see wave plan stop condition). For now, the advisory second opinion is deliberation-level only.

## Agent Memory Strategy

Two memory systems coexist — they serve different purposes:

| System | Location | Purpose | Scope |
|--------|----------|---------|-------|
| **SDK memory** | `.agent_memory/findings.json` | Structured regression tracking: stores findings, links to PRs, detects regressions across runs | Centralized, all agents |
| **Native memory** | `.claude/agent-memory/<agent-name>/MEMORY.md` | Per-agent persistent context: each native subagent has its own `MEMORY.md` for cross-session learning | Per-agent, independent |

**SDK memory** is the canonical findings ledger for `run_review.py`. It enables regression warnings ("this file had a CRITICAL finding last run") and pattern tracking. **Native memory** helps individual subagents remember project context across interactive sessions (e.g., "last time I reviewed eval_seed.py, I found X").

Neither replaces the other. Do not deprecate `.agent_memory/` — it provides structured cross-run regression tracking that native per-agent memory cannot.

## Parallel Execution Architecture

**SDK orchestrator (`run_review.py`)** uses Python asyncio to run agents in parallel groups. This provides:
- Deterministic control: agent ordering, phased execution (hard gates → depth agents → founder agents)
- Unified report synthesis and verdict aggregation
- Configurable retry with backoff on failures

**Native subagents** can run in background via Claude Code's built-in background execution (`run_in_background` for Bash tool, `background: true` frontmatter for subagents, or Ctrl+B to background a running task), but this is ad-hoc and doesn't provide the deterministic control plane of `run_review.py`.

**Decision (2026-03-11):** The asyncio orchestration in `run_review.py` is not
replaced inside the legacy SDK review lane. That decision does not make it the
current Codex wave path when executor config disables SDK agent review.

## Agent Teams (Evaluation — Parked)

Claude Code's Agent Teams feature allows multiple subagents to collaborate on tasks with shared context. As of 2026-03-11, this feature is **experimental and disabled by default** per official Anthropic documentation, with known limitations.

**What it would enable:** Multiple native subagents reviewing code simultaneously with coordination — similar to `run_review.py` but without the SDK. Could eventually replace the asyncio orchestrator if it stabilizes.

**Decision (2026-03-11):** PARKED. Feature is experimental and disabled by default, API may change. Revisit when Agent Teams stabilizes and has mature documentation. Current two-system architecture (native ad-hoc + SDK batch) is sufficient.

## Execution-Aware Review (S1-C Lesson)

**Background:** S1-C (PR #606) proved that static-only agent review misses real bugs. The bridge (Codex) caught 4 bugs that all 4 SDK agents missed because the bridge executes code while agents only read source text.

**Change:** All 5 review agents (adversary, verifier, expert, structural-proof, grounding) now have `Bash` tool access and "Execution Verification" sections in their prompts. They are instructed to run targeted commands as part of their review.

**What agents should now do:**

| Agent | Execution Focus |
|-------|----------------|
| **Adversary** | Repro vulnerability claims with Python/Node scripts; verify fail-closed behavior |
| **Verifier** | Run evidence commands from tracker notes; run ratchet checks; verify gate tests |
| **Structural-proof** | Execute projections on sample inputs; verify seed counts; run structural tests |
| **Grounding** | Run reviewed test files; verify test classification; check theater risk |
| **Expert** | Verify dead-code claims with grep + test runs; quantify DRY violations |

**Scope constraints:** All agents are restricted to repo-local commands. No network access, no file creation outside `.scratch/`, no destructive operations.

**Rollout:** Grounding and adversary benefit most. Verifier next. Structural-proof last (narrow repo-local helper commands preferred over free-form shell).

## Notes

- SDK orchestrators run agents **in parallel** for speed
- Native subagents run via Claude Code's built-in Agent tool (can also run in background)
- Prompt source of truth: `tools/agents/*_prompt.md`
- Native agent files: `.claude/agents/*.md` (generated — do not edit directly)
- SDK agent memory: `.agent_memory/findings.json`
- Native agent memory: project-scoped (`.claude/agent-memory/<agent-name>/MEMORY.md`)
- Session transcripts persist in `.claude/sessions/`
- See `mu/docs/agents/AgentGuardrails.v0.md` for format requirements
- See `mu/docs/agents/AgentRig.v0.md` for architecture and trust model
- See `mu/docs/agents/NoOpProofTemplate.v0.md` for structured NO-OP evidence when correct action is "do nothing"
