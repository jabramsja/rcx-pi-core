# RCX Rewrite Termination Contracts (Frozen)

## Scope
These contracts define **termination semantics** for rewrite evaluation and trace emission. They are intended to prevent future tightening-by-accident while still allowing runtime evolution.

This document is **contract-only**: it defines observable obligations, not internal algorithms.

## Definitions
- **Rewrite step**: one application of a rewrite rule that produces a successor state.
- **Trace-shaped JSON**: any JSON payload emitted by tooling/CLIs representing successive rewrite states.
- **Termination**: evaluation stops and emits a final state (or a halt classification) for one of the reasons below.

## Halt reasons (canonical enum)
A producer MAY classify termination using one of these **canonical reasons**:

- `completed`: no applicable rules remain (normal form / fixed point).
- `max_steps`: stopped because a configured step budget was exhausted.
- `loop_detected`: stopped because a repeated state (cycle) was detected.
- `error`: stopped due to parse/eval/runtime error (must include an error message).
- `external_abort`: stopped due to user/host cancellation (signal, timeout, etc).

Notes:
- Producers MAY omit this classification entirely (backward compatibility).
- If a halt reason is present, it MUST be one of the above strings.

## Required invariants (do not break)
These apply to any trace-shaped output a consumer might use to reason about termination:

1. **Monotone step count**: if steps are representable, the step index MUST be monotone increasing from the start of the trace.
2. **Determinism within a run**: within a single run, the sequence of states in the trace MUST reflect the actual rewrite sequence (no reordering).
3. **No tightening**: termination metadata is OPTIONAL unless explicitly stated otherwise by a schema version upgrade.

## Optional termination metadata (recommended)
Producers MAY include termination metadata (at top-level or within a trace object) such as:

- `steps`: integer, number of steps performed
- `max_steps`: integer, configured step budget
- `halt_reason`: one of the canonical enum strings above
- `loop`: object describing loop detection (e.g., first_repeat_step, period)
- `error`: object/string describing failure details (only if halt_reason=`error`)

If included:
- `steps` SHOULD be present and non-negative
- `halt_reason` SHOULD be present
- `max_steps` SHOULD be present when `halt_reason=max_steps`

## Consumer tooling contract (inspection tools)
Tooling that inspects trace-shaped JSON SHOULD:
- treat missing termination metadata as "unknown"
- compute `steps` from the trace length when possible
- offer loop detection as a best-effort inference (not a proof)

## Backward compatibility
These contracts MUST NOT force current producers to change output shape. They only constrain meaning if/when termination metadata is present.
