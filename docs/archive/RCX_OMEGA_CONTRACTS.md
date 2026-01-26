# RCX-Ω Contracts (Frozen)

Status: **ALL GREEN** (pytest fully passing at time of freezing).

This document freezes the externally visible contracts for the RCX-Ω CLI surface and its JSON interchange formats.

## Scope

Applies to these CLIs:

- `trace_cli`
- `omega_cli`
- `analyze_cli`

And these JSON interchange shapes:

- **Trace-shaped JSON** (stepwise execution trace)
- **Omega-summary JSON** (summary output; may omit steps unless `--trace` is provided)

## Non-Goals

- This contract does not freeze internal Python classes/fields.
- This contract does not guarantee stable ordering of JSON object keys.
- This contract does not guarantee stable numeric values beyond “present + type + meaning”.

---

## CLI Contracts

### 1) trace_cli

**Purpose:** Emit trace-shaped JSON.

**Output:** Always emits a single JSON object (UTF-8) to stdout.

**Shape:** Trace-shaped JSON (see “JSON Contracts: Trace-shaped”).

**Guarantees:**
- Output is valid JSON.
- Includes `steps[]`, `stats`, and a convergence marker.

### 2) omega_cli

**Purpose:** Emit omega-summary JSON by default; optionally emit trace-shaped JSON.

**Flags:**
- Default: emits **omega-summary JSON**
- `--trace`: emits **trace-shaped JSON** compatible with `analyze_cli`

**Guarantees:**
- Default output is valid JSON and contains the omega summary “result” information.
- When `--trace` is set, output conforms to trace-shaped JSON and is accepted by `analyze_cli`.

### 3) analyze_cli

**Purpose:** Analyze either trace-shaped JSON or omega-summary JSON.

**Input:** Reads a single JSON object from stdin.

**Accepted inputs:**
- Trace-shaped JSON
- Omega-summary JSON

**Hard guarantees:**
- MUST NOT assume internal `TraceStep` fields.
- Per-step metrics are derived from **motifs** (pattern-level signals), not private step struct internals.
- Works when omega JSON omits `steps` (unless `--trace` was used upstream).

**Stable output markers (required by tests):**
Analyze output ALWAYS includes:

- `== Ω analyze ==`
- For omega-summary analysis: includes `classification:`
- For trace analysis: includes `converged:`

---

## JSON Contracts

### A) Trace-shaped JSON (frozen shape)

A **trace-shaped** JSON object has (at minimum) the following top-level members:

- `steps`: array
- `stats`: object
- convergence marker (field name frozen by behavior; analyze output must include `converged:` when analyzing traces)

#### Required (logical) constraints
- `steps` is an array of JSON objects.
- `stats` is an object.

#### Step objects
Step objects are intentionally treated as *extensible*. `analyze_cli` must not depend on private fields.

Instead:
- Step interpretation happens via **motifs** (signals/labels/patterns that can be computed or present).
- If motifs are absent, analysis degrades gracefully (no crash; reduced metrics).

### B) Omega-summary JSON (frozen shape)



Note: fields beyond the frozen minimum (e.g., `seed`) MAY appear, but they are OPTIONAL and not part of the frozen minimum.
The frozen minimum remains: `result`.
An **omega-summary** JSON object has (at minimum) the following top-level members:

- `result`: present (type is implementation-defined but must be JSON-serializable)

And it MAY include:

- `steps` (if `--trace` is used, then this becomes trace-shaped JSON instead)

#### Required (logical) constraints
- `result` exists.
- `steps` may be absent. `analyze_cli` must handle this.

---


## Runtime Reality Notes (Current Behavior)

These notes document **current** observed runtime behavior. They do not add new requirements.

- `kind`:
  - May be **omitted**, or may appear with **legacy values** (e.g. `omega`).
  - `kind = omega_summary` is a **future target** and is **not** a frozen requirement today.
- `schema_version`:
  - Is **OPTIONAL** and **MUST remain opt-in**.
  - Producers may inject it only when `RCX_OMEGA_ADD_SCHEMA_FIELDS=1` is set.
  - Default output MUST remain unchanged when the env var is not set.
- Consumers (including `analyze_cli`) MUST remain tolerant:
  - Do not require `kind` or `schema_version`.
  - Continue accepting both trace-shaped and omega-summary JSON as defined by the frozen contracts.


## Schema Versioning Policy (frozen policy, optional fields)

We introduce schema definitions (see `schemas/rcx-omega/`) with explicit version labels.

### Definitions
- **schema_version**: semantic version of the JSON schema document governing the payload shape.
- **kind**: discriminator identifying payload family: `trace` or `omega_summary`.

### Backward compatibility rules
- Adding OPTIONAL fields: MINOR bump.
- Adding REQUIRED fields or changing meaning/type: MAJOR bump.
- Bugfix in schema text without shape change: PATCH bump.

### Runtime adoption strategy (recommended)
- Short-term: code MAY omit `schema_version` and `kind` to preserve existing outputs.
- Medium-term: code adds `schema_version` + `kind` as OPTIONAL fields (tests updated accordingly).
- Long-term: code can require them only on a MAJOR bump.

---

## Compatibility Matrix

| Producer \ Consumer | analyze_cli |
|---|---|
| trace_cli (trace-shaped) | ✅ must accept |
| omega_cli default (omega-summary) | ✅ must accept |
| omega_cli --trace (trace-shaped) | ✅ must accept |

---

## Test-Implied Invariants (do not break)
- `analyze_cli` prints `== Ω analyze ==` always.
- If analyzing omega-summary, output includes `classification:`
- If analyzing trace-shaped, output includes `converged:`

## Env-gated optional schema fields

### Trace-shaped outputs (trace_cli and omega_cli --trace)
- When `omega_cli --trace` emits **trace-shaped JSON**, it is compatible with `analyze_cli`.
- Schema metadata fields remain **optional and opt-in**.
- If and only if `RCX_OMEGA_ADD_SCHEMA_FIELDS=1` is set, producers MAY inject:
  - `schema_version` (if injected, SHOULD be present and semver-formatted)
  - `kind` (only if absent)
- Default behavior (env var unset) MUST remain unchanged.
