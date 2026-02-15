<!--
DOC_STATUS
TYPE: DESIGN_SPEC
LAST_VERIFIED: 2026-02-10
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: tests/structural/test_observer_events.py

This header enables automated doc drift detection.
- REFERENCE: Stable definitions, rarely changes
- DESIGN_SPEC: Architectural intent, may diverge from implementation
- IMPLEMENTATION: Active development, should match current code

If this doc's claims don't match reality, update the doc or fix the code.
Run: pytest tests/docs/test_doc_contracts.py -v
-->

# Observer Event Contract v0

## Purpose

Define a canonical event schema and ordering contract for observability in the RCX engine pipeline. Events must be deterministic, hashable, and substrate-neutral so that Python and JS traces can be compared structurally.

**Scope:** N6a = schema + canonicalization contract (this document).
N6b = cross-substrate isomorphic stream comparison (out of scope, deferred).

## Event Schema (v0)

Every observer event is a JSON-compatible dict with exactly these required fields:

| Field | Type | Description |
|-------|------|-------------|
| `event_name` | string | Identifies the event point (e.g. `"step_boundary"`, `"stall_detected"`) |
| `step` | integer ≥ 0 | Monotonically increasing step counter within a pipeline run |
| `state_hash` | string \| null | Content hash of the current Mu state at event time; null if not yet computed |
| `error_code` | string \| null | Dotted error code (per existing taxonomy) if this event represents a failure; null otherwise |
| `substrate` | string | `"python"` or `"js"` — which substrate emitted the event |
| `timestamp` | integer ≥ 0 | Logical clock value (NOT wall-clock); monotonically increasing per substrate per run |

### Field Invariants

1. `event_name` must be one of the registered event names (see Mandatory Event Points below).
2. `step` must be non-negative. Within a single pipeline run, step values are non-decreasing (multiple events may share a step).
3. `state_hash` must be a hex string or null. When present, it must be the output of `mu_hash` on the current state.
4. `error_code` must be null on success events. On failure events, it must be a dotted code from the existing error taxonomy.
5. `substrate` must be `"python"` or `"js"`. No other values.
6. `timestamp` is a logical counter, not wall-clock. Starts at 0 per run, increments by 1 per event emitted on that substrate.

## Event Ordering and Canonicalization

### Ordering Rules

Events within a single pipeline run are ordered by:

1. **Primary sort:** `step` (ascending, integer comparison)
2. **Tie-break:** `timestamp` (ascending, integer comparison)

This produces a deterministic total order for any event stream from a single substrate. Cross-substrate comparison (N6b) will pair events by `(step, event_name)` tuples.

### Canonical JSON Serialization

For hashability and cross-substrate comparison, events are serialized with:

1. Keys sorted alphabetically (Python: `json.dumps(sort_keys=True)`, JS: sorted `Object.keys()`)
2. No whitespace (`separators=(',', ':')` in Python, no space in JS)
3. UTF-8 encoding
4. No trailing newline

This ensures `sha256(canonical_json(event))` produces identical hashes on both substrates for identical event payloads.

## Mandatory Event Points (Python, v0)

| Event Name | When Emitted | error_code |
|------------|-------------|------------|
| `step_boundary` | At each engine iteration boundary (pre-step state) | null |
| `stall_detected` | When the engine detects a stall (no progress) | null (stall is a signal, not an error) |
| `closure_detected` | When recurrence detection finds a closure | null |
| `fail_closed` | When a fail-closed guard triggers (bad shape, cycle, etc.) | required (from error taxonomy) |

### Event Point Semantics

- **`step_boundary`**: Emitted at each iteration boundary of `run_engine_pipeline`, capturing the current state *before* the projection step produces `next_state`. `state_hash` reflects the pre-transition engine state. This is the heartbeat of the event stream. Rationale: snapshotting pre-step state is deterministic and unambiguous in fail-closed paths (the state that caused the failure is always recorded).
- **`stall_detected`**: Emitted when `run_engine_pipeline` detects that the engine has stalled (non-terminal state with no progress). `state_hash` reflects the stalled state.
- **`closure_detected`**: Emitted when recurrence detection sets `closure_detected=true`. `state_hash` reflects the state at closure.
- **`fail_closed`**: Emitted when any fail-closed validation rejects input. `error_code` is mandatory and must match the existing dotted error taxonomy (e.g. `input.shape_mismatch`, `trace.cycle_detected`).

## Parity Intent

- **N6a** (this document): Defines the event schema, field invariants, ordering rules, and canonical serialization contract. Grounding tests validate schema shape and canonicalization determinism using test-local fixtures only.
- **N6b** (IMPLEMENTED): Cross-substrate isomorphic stream comparison. `run_engine_pipeline` in both `step_mu.py` and `eval_step.js` accepts an optional `observer` parameter (list/array). When provided, events are appended at each mandatory event point. JS JSON API exposes `observer: true` on `run_engine_pipeline` and `run_engine_with_routing` actions, returning `observer_events` in the response. Tests in `tests/test_js_parity_automated.py::TestObserverIsomorphism` verify pairwise equality of normalized event streams.

## Non-Goals

1. **No semantic changes** to the engine or hemisphere routing. Observer events are read-only telemetry.
2. **No adaptive routing.** Events do not influence execution flow.
3. **No metabolization logic.** Metabolization is a separate VECTOR concern (see `mu/docs/roadmap/MuHemispheresDesign.md`).
4. **No wall-clock timestamps.** Logical ordering only — wall-clock breaks determinism.
5. **No event persistence.** Storage and replay are out of scope for v0.

## Related Documents

- `mu/docs/core/RCXEngine.v0.md` — Engine pipeline that emits events
- `mu/docs/roadmap/MuHemispheresDesign.md` — Hemisphere routing (events observe, never influence)
- `TASKS.md` — Authorization and promotion tracking
