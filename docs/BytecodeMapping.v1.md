# Bytecode VM Mapping v1

Status: VECTOR (design-first, no code changes)

This document upgrades BytecodeMapping.v0.md to v1 by specifying a minimal bytecode VM model that aligns with the RCX-π execution lifecycle:

MATCH → REDUCE or STALL → (optional FIX) → FIXED → continue

v1 clarifies how STALL/FIX participate in execution (not just reserved opcodes), while keeping the system replayable and trace-driven.

## Goals

- Define an execution loop that produces trace events consistent with v2 validation.
- Map conceptual phases (MATCH/REDUCE/STALL/FIX) to bytecode operations.
- Specify what state belongs in registers vs what is derived from the trace.
- Preserve "anti-theater" invariants: progress must be observable as value transitions or explicit stalls.

## Non-goals

- Full instruction set for all motifs and reductions.
- Performance optimizations.
- Self-hosting bytecode compiler in this doc.
- Defining new trace schemas beyond existing v2 fields.

## Model overview

The VM is an interpreter over a linear bytecode stream. It evaluates a current value in registers, applies pattern rules, and emits trace events.

There are two distinct representations:

1. Execution state (registers): what the VM actively mutates.
2. Trace state (events): the public, canonical record that must be sufficient to validate behavior.

Key rule: replay validation depends on the trace, but the VM must be able to emit that trace without private coupling to the validator.

## Registers (v1)

Minimum register file:

- R0: value (mu object)
- RH: current_value_hash (derived from R0 via canonical hash function)
- RP: current_pattern_id (the pattern site currently being matched)
- RS: status enum {ACTIVE, STALLED}
- RF: pending_fix_target_hash (optional; used only when status is STALLED)

Additional optional registers:

- RI: instruction pointer
- RC: counters (stall/fix/fixed), though these can be derived from the trace

## Trace events (v2 alignment)

The VM emits these v2 execution events:

- execution.stall
  - mu.value_hash = RH
  - mu.pattern_id = RP

- execution.fix (optional)
  - mu.target_hash = RF (must equal RH at time of stall)

- execution.fixed
  - mu.before_hash
  - mu.after_hash

v1 treats these events as first-class outputs of VM execution.

## Bytecode operations

v1 defines a minimal set of operations sufficient to express MATCH/REDUCE/STALL/FIX:

### Core ops

- OP_MATCH pattern_id
  - Sets RP = pattern_id
  - Attempts to match RP against the current value R0

- OP_REDUCE rule_id
  - Applies a reduction rule to R0
  - Updates R0 and RH
  - Emits execution.fixed with (before_hash, after_hash)
  - Sets RS = ACTIVE

- OP_STALL
  - Declares no reduction is available for the current (RH, RP)
  - Emits execution.stall with (value_hash=RH, pattern_id=RP)
  - Sets RS = STALLED
  - Clears RF unless already set by a fix plan

### Fix ops

- OP_FIX target_hash
  - Allowed only when RS == STALLED
  - Requires target_hash == RH
  - Sets RF = target_hash
  - Emits execution.fix(target_hash=RF)
  - Does NOT change R0/RH

- OP_FIXED after_value
  - Allowed only when RS == STALLED
  - Requires RF is None or RF == RH (depending on whether fix is optional at this stall)
  - Computes after_hash from after_value
  - Emits execution.fixed(before_hash=RH, after_hash=after_hash)
  - Sets R0 = after_value; RH = after_hash
  - Sets RS = ACTIVE
  - Clears RF

Notes:
- execution.fix is optional in the trace. Therefore OP_FIXED must be valid whether OP_FIX occurred or not.
- The constraints above match the existing replay_cli validation semantics.

## Execution loop semantics

High-level loop:

1. ACTIVE:
   - OP_MATCH(pattern_id)
   - If a reduction exists:
       - OP_REDUCE(rule_id)
     Else:
       - OP_STALL

2. STALLED:
   - Either:
     - Provide OP_FIX(RH) then OP_FIXED(after_value), OR
     - Provide OP_FIXED(after_value) directly (fix absent)
   - Return to ACTIVE after OP_FIXED

This captures the reality that "stall" is a public state and "fix/fixed" is an explicit transition out of it.

## Determinism and anti-theater invariants

### Deterministic hashing

- RH must be computed via the canonical hash used everywhere else.
- A change in R0 must change RH (unless it is structurally identical).

### No-op prevention

- OP_REDUCE and OP_FIXED must produce after_hash that differs from before_hash unless the semantics explicitly allow idempotent transitions (discouraged).
- If idempotence is allowed for a specific rule, it must be justified and observable.

### Stall integrity

- OP_STALL cannot be emitted while RS == STALLED (no double-stall without leaving stall).
- Stalling twice at the same (RH, RP) without an intervening RH change is a closure condition and should be recognized by higher-level semantics (see IndependentEncounter.v0.md).

## What lives in registers vs trace

Registers are authoritative during execution.
Trace is authoritative for post-hoc validation.

Guideline:
- Anything needed for validation must be emitted into the trace as public fields.
- The VM may compute derived values (counts, summaries), but these must always be derivable from the event stream.

## Mapping MATCH/REDUCE/STALL/FIX to ops

- MATCH: OP_MATCH(pattern_id)
- REDUCE: OP_REDUCE(rule_id) → emits execution.fixed
- STALL: OP_STALL → emits execution.stall
- FIX: OP_FIX(target_hash) + OP_FIXED(after_value) → emits execution.fix (optional) and execution.fixed

## Recommended minimal opcode table (v1)

- 0x10 OP_MATCH
- 0x20 OP_REDUCE
- 0x30 OP_STALL
- 0x40 OP_FIX
- 0x41 OP_FIXED

Exact numeric values are placeholders; only the semantic separation matters in v1.

## Example trace-producing run

Scenario: value stalls, then is fixed.

- Start ACTIVE, RH = H0
- OP_MATCH(P1)
- no reduction
- OP_STALL → emit execution.stall(value_hash=H0, pattern_id=P1)
- RS = STALLED
- OP_FIX(H0) → emit execution.fix(target_hash=H0)
- OP_FIXED(value'=V1) → compute H1, emit execution.fixed(before_hash=H0, after_hash=H1)
- RS = ACTIVE

## Compatibility notes

- This design remains compatible with existing replay validation rules.
- The VM does not need to import or consult the validator; it only needs to obey constraints that are already trace-validated.

## v1 upgrades vs v0

- STALL/FIX are not merely reserved concepts; they are executable transitions with strict constraints.
- Execution loop is explicitly defined.
- Registers and trace responsibilities are separated and documented.
