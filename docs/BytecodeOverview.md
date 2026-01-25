# Bytecode VM Overview

Quick reference for bytecode-related files.

## File Map

| What | Where |
|------|-------|
| Implementation | `rcx_pi/bytecode_vm.py` |
| Tests | `tests/test_bytecode_vm_v0.py` |
| Audit | `tools/audit_bytecode.sh` |
| v0 Design (replay) | `docs/BytecodeMapping.v0.md` |
| v1 Design (execution) | `docs/BytecodeMapping.v1.md` |

## Implementation Status

| Version | Scope | Status |
|---------|-------|--------|
| v0 | Replay-only (10 opcodes) | ✅ Complete |
| v1a | OP_STALL (stall declaration) | ✅ Complete |
| v1b | OP_FIX/OP_FIXED (stall resolution) | ✅ Complete |
| v1c | OP_MATCH/OP_REDUCE (execution loop) | Not started |

## Current Opcodes

**v0 (replay):** INIT, LOAD_EVENT, CANON_EVENT, STORE_MU, EMIT_CANON, ADVANCE, SET_PHASE, ASSERT_CONTIGUOUS, HALT_OK, HALT_ERR

**v1a/v1b (execution):** STALL, FIX, FIXED

**Reserved:** ROUTE, CLOSE

## Registers (v1)

| Register | Purpose |
|----------|---------|
| RS | Execution status (ACTIVE/STALLED) |
| RP | Current pattern_id |
| RH | Current value_hash |
| RF | Pending fix target hash |

## What's Implemented vs Not

**Implemented:**
- State machine (ACTIVE ↔ STALLED)
- Constraint checking (no double-stall, hash validation)
- Closure detection (second independent encounter)
- Replay validation

**Not implemented:**
- R0 (actual value storage)
- OP_MATCH (pattern matching)
- OP_REDUCE (rule application)
- Execution loop orchestration
- Fix sourcing (where new values come from)

## Tests

78 tests covering:
- Opcode unit tests
- Event mapping (trace.start, step, trace.end)
- Golden round-trip (v1 fixtures)
- Rejection cases
- Reserved opcode guards
- v1a STALL execution
- v1b FIX/FIXED execution
- Closure detection
