# RCX Agent Rig - Lead Architect Workflow

## Overview

The Agent Rig is a multi-agent system that validates code changes before merge. It addresses the "fish swimming upstream" problem: using an LLM (trained on Python) to enforce structural computation principles it rarely sees.

**Key Insight:** We don't trust any single agent. We trust the **fight** between agents.

## The Rig Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     1. CONTRABAND LINTER                        │
│                  (Dumb regex - no AI needed)                    │
│              Blocks: eval, exec, globals, pickle                │
│                   FAILS? → Stop. Don't wake AI.                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓ PASS
┌─────────────────────────────────────────────────────────────────┐
│                       2. THE BUILDER                            │
│                     Expert Agent (Sonnet)                       │
│              Writes code, suggests simplifications              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                  3. THE CRITICS (Parallel)                      │
│  ┌─────────────────────┐    ┌─────────────────────┐            │
│  │  Verifier (Sonnet)  │    │  Adversary (Sonnet) │            │
│  │  Checks invariants  │    │  Attacks code       │            │
│  │  North Star rules   │    │  Edge cases         │            │
│  └─────────────────────┘    └─────────────────────┘            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      4. THE JUDGE                               │
│               Structural-Proof Agent (Sonnet)                   │
│         Demands JSON projections, runs verification code        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    5. THE GROUNDING                             │
│                Grounding Agent (Sonnet)                         │
│         Converts claims into executable pytest tests            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    6. THE TRANSLATOR                            │
│               Translator Agent (Sonnet)                         │
│      Explains code in plain English for founder approval        │
└─────────────────────────────────────────────────────────────────┘

## Agents

### 1. Contraband Linter (`tools/contraband.sh`)
- **Type:** Bash script (no AI)
- **Purpose:** Block obviously dangerous patterns before waking up AI
- **Blocks:** `eval()`, `exec()`, `globals()`, `locals()`, `pickle`, metaclass dunders
- **Run:** Before any AI agent

### 1b. AST Police (`tools/ast_police.py`)
- **Type:** Python AST parser (no AI)
- **Purpose:** Catch what grep misses (set literals, multiline tricks, aliasing)
- **Blocks:** Set comprehensions, walrus operator, yield, async, dangerous builtins via alias
- **Allows:** Key comparison sets `{"head", "tail"}`, lines marked `# AST_OK:`
- **Why:** Grep reads text. AST reads grammar. Can't fool grammar.

### 2. Expert (`expert.md`)
- **Model:** Sonnet
- **Purpose:** Write code, identify complexity, suggest simplifications
- **Focus:** Minimalism, emergent patterns, self-hosting readiness
- **Verdict:** MINIMAL / COULD_SIMPLIFY / OVER_ENGINEERED

### 3. Verifier (`verifier.md`)
- **Model:** Sonnet (upgraded from Haiku)
- **Purpose:** Check North Star invariants
- **Focus:** Host smuggling, Mu type integrity, lambda prevention, determinism
- **Verdict:** APPROVE / REQUEST_CHANGES / NEEDS_DISCUSSION

### 4. Adversary (`adversary.md`)
- **Model:** Sonnet (upgraded from Haiku)
- **Purpose:** Break things, find vulnerabilities
- **Focus:** Type confusion, lambda smuggling, non-determinism, edge cases
- **Verdict:** SECURE / VULNERABLE / NEEDS_HARDENING

### 5. Structural-Proof (`structural-proof.md`)
- **Model:** Sonnet
- **Purpose:** Demand concrete proof that operations are structural
- **Focus:** Actual JSON projections, manual traces, edge case verification
- **Enhancement:** Must generate runnable Python verification code
- **Verdict:** PROVEN / UNPROVEN / IMPOSSIBLE_AS_CLAIMED

### 6. Grounding (`grounding.md`)
- **Model:** Sonnet
- **Purpose:** Convert structural claims into executable tests
- **Focus:** No mocks, no stubs - actual kernel execution
- **Rule:** If you can't write the test, the claim is ungrounded
- **Verdict:** GROUNDED / UNGROUNDED / PARTIALLY_GROUNDED

### 7. Translator (`translator.md`)
- **Model:** Sonnet
- **Purpose:** Explain code to non-technical founder
- **Focus:** Plain English, host smuggling detection, intent checking
- **Detects:** Scope creep, oversimplification, deviation from request
- **Verdict:** MATCHES_INTENT / DEVIATES / NEEDS_DISCUSSION

### 8. Fuzzer (`fuzzer.md`)
- **Model:** Sonnet
- **Purpose:** Property-based testing with 1000+ random inputs
- **Focus:** Roundtrip properties, parity, idempotency, no-crash
- **Tool:** Uses Python `hypothesis` library
- **Why:** AI can lie to you, but cannot lie to 1000 random CPU-generated inputs
- **Verdict:** ROBUST / FRAGILE / BROKEN

### 9. Visualizer (`visualizer.md`)
- **Model:** Haiku (cheap, run often)
- **Purpose:** Draw Mu structures as Mermaid diagrams
- **Focus:** Visual lie detection - linked lists show chains, Python lists show blobs
- **Why:** Founder can't read code but CAN look at a picture
- **Red flag:** Any red "blob" node = Python list smuggled in
- **Output:** Mermaid diagram (renders in GitHub, VS Code, etc.)

## Key Design Decisions

### Intelligence Balance
- **Rule:** Reviewers must be at least as smart as the builder
- **Before:** Expert=Sonnet, Adversary=Haiku (unsafe)
- **After:** All agents use Sonnet (balanced)

### Trust Model
- We don't trust the Expert's code
- We don't trust the Verifier's approval
- We trust the **conflict** between them
- If Adversary can't break it AND Verifier approves AND Structural-Proof is satisfied, then merge

### Parallelization
- Verifier and Adversary run in parallel (independent)
- Cuts review time in half

### The "No Hallucination" Rule
- Structural-Proof must generate runnable code, not just text traces
- Grounding must write actual pytest tests
- Text can lie. Code that crashes doesn't lie.

### The Trusted Kernel Architecture
- **The Law (Kernel):** `eval_seed.py` contains `step()`, `match()`, `substitute()`
- **The Lawyers (Claude):** Claude writes JSON projections (data)
- **The Rule:** Claude writes DATA. Kernel executes DATA. If kernel crashes, Claude lied.
- **Enforcement:** Kernel files should be treated as read-only after initial bootstrap
- This architecture makes it mathematically impossible for Claude to smuggle host semantics - JSON simply doesn't support Python features

## Usage

### MANDATORY: Run ALL Agents Before Merge

**For any code change, run these agents in parallel:**

| Agent | Purpose | Always Run? |
|-------|---------|-------------|
| **verifier** | Check RCX invariants | ✅ YES |
| **adversary** | Red team / attack code | ✅ YES |
| **expert** | Simplicity review | ✅ YES |
| **structural-proof** | Verify structural claims | ✅ YES |
| **grounding** | Write executable tests | ✅ YES (if claims made) |
| **fuzzer** | Property-based testing | ✅ YES (for core code) |
| **translator** | Plain English explanation | ⚠️ On request |
| **visualizer** | Mermaid diagrams | ⚠️ On request |

**Minimum for ALL changes:** verifier, adversary, expert, structural-proof (4 agents)
**For core kernel/seed code:** Add grounding, fuzzer (6 agents)
**For founder review:** Add translator, visualizer (8 agents)

### Workflow

```bash
# 1. Run linters first (free, fast)
./tools/contraband.sh rcx_pi
python3 tools/ast_police.py

# 2. Run ALL mandatory agents in PARALLEL via Claude Code
# (In a single message with multiple Task tool calls)
```

### In Claude Code Session

```
# ALWAYS run these 4 in parallel for any code change:
[Task: verifier] "Verify <feature> implementation"
[Task: adversary] "Attack <feature> implementation"
[Task: expert] "Review <feature> for simplicity"
[Task: structural-proof] "Verify structural claims in <feature>"

# For core code, also run:
[Task: grounding] "Write tests for <feature> claims"
[Task: fuzzer] "Property-based tests for <feature>"

# For founder review:
[Task: translator] "Explain <feature> in plain English"
[Task: visualizer] "Draw Mu structures in <feature>"
```

### Agent Checklist (Copy for PR)

```markdown
## Agent Review
- [ ] verifier:
- [ ] adversary:
- [ ] expert:
- [ ] structural-proof:
- [ ] grounding: (if applicable)
- [ ] fuzzer: (if applicable)
- [ ] translator: (on request)
- [ ] visualizer: (on request)
```

## Files

| File | Purpose |
|------|---------|
| `.claude/agents/expert.md` | Builder agent config |
| `.claude/agents/verifier.md` | Invariant checker config |
| `.claude/agents/adversary.md` | Red team attacker config |
| `.claude/agents/structural-proof.md` | Proof demander config |
| `.claude/agents/grounding.md` | Test writer config |
| `.claude/agents/translator.md` | Plain English explainer config |
| `.claude/agents/fuzzer.md` | Chaos monkey / property-based testing |
| `.claude/agents/visualizer.md` | Mermaid diagram generator |
| `tools/contraband.sh` | Dumb regex linter (no AI) |
| `tools/ast_police.py` | AST-based linter (catches what grep misses) |

## History

| Date | Change |
|------|--------|
| 2026-01-26 | Initial rig: expert, verifier, adversary, structural-proof |
| 2026-01-26 | Upgraded verifier/adversary from Haiku to Sonnet |
| 2026-01-26 | Added grounding agent (test writer) |
| 2026-01-26 | Added translator agent (plain English) |
| 2026-01-26 | Enhanced structural-proof with "No Hallucination" rule |
| 2026-01-26 | Created contraband.sh linter |
| 2026-01-26 | Added fuzzer agent (Hypothesis property-based testing) |
| 2026-01-26 | Documented Trusted Kernel architecture |
| 2026-01-26 | Added visualizer agent (Mermaid diagrams) |
| 2026-01-26 | Added ast_police.py (catches what grep misses) |
