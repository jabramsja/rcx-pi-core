"""
RCX Bytecode VM v0 - Replay-only bytecode execution.

This module implements a minimal bytecode VM sufficient for deterministic replay
of v1 trace events. It does NOT implement execution semantics (stall/fix/route).

Design doc: docs/BytecodeMapping.v0.md

Feature flag: RCX_BYTECODE_V0=1 to enable bytecode validation during replay.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple

from rcx_pi.trace_canon import canon_event, _deep_sort_json

# Feature flag
RCX_BYTECODE_V0_ENABLED = os.environ.get("RCX_BYTECODE_V0", "0") == "1"


class Phase(Enum):
    """VM execution phase."""
    START = auto()
    RUNNING = auto()
    END = auto()
    HALTED = auto()


class Opcode(Enum):
    """
    Bytecode opcodes for v0 replay.

    v0 opcodes (implemented):
    - INIT through HALT_ERR: Core replay operations

    Reserved opcodes (NOT implemented in v0):
    - STALL, FIX, ROUTE, CLOSE: Blocked until VECTOR promotion

    Debug opcodes (v2 observability only):
    - DBG_STALL, DBG_APPLIED, DBG_NORMAL: No state change, gated by RCX_TRACE_V2
    """
    # v0 Core opcodes
    INIT = auto()
    LOAD_EVENT = auto()
    CANON_EVENT = auto()
    STORE_MU = auto()
    EMIT_CANON = auto()
    ADVANCE = auto()
    SET_PHASE = auto()
    ASSERT_CONTIGUOUS = auto()
    HALT_OK = auto()
    HALT_ERR = auto()

    # Reserved opcodes (v1+ only, blocked in v0)
    # These are defined for documentation but must not be executed
    STALL = auto()
    FIX = auto()
    ROUTE = auto()
    CLOSE = auto()

    # Debug opcodes (v2 observability, no state change)
    DBG_STALL = auto()
    DBG_APPLIED = auto()
    DBG_NORMAL = auto()


# Reserved opcodes that must not be executed in v0
RESERVED_OPCODES = frozenset([Opcode.STALL, Opcode.FIX, Opcode.ROUTE, Opcode.CLOSE])

# Valid v1 event types for replay
V1_EVENT_TYPES = frozenset(["trace.start", "step", "trace.end"])


@dataclass
class Cursor:
    """VM cursor state."""
    i: int = 0
    phase: Phase = Phase.START


@dataclass
class Artifacts:
    """VM output artifacts."""
    canon_out: str = ""
    error: Optional[str] = None


@dataclass
class Instruction:
    """A single bytecode instruction."""
    opcode: Opcode
    args: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        if self.args:
            args_str = ", ".join(f"{k}={v!r}" for k, v in self.args.items())
            return f"{self.opcode.name}({args_str})"
        return self.opcode.name


class BytecodeVMError(Exception):
    """Error during bytecode VM execution."""
    pass


class BytecodeVM:
    """
    Minimal bytecode VM for v0 replay.

    State model (per BytecodeMapping.v0.md section 3):
    - mu_store: Map from event index to mu payload
    - buckets: Routing state (declared but not modified in v0)
    - cursor: Current position and phase
    - artifacts: Output accumulator and error state

    v0 is replay-only: it validates and canonicalizes trace events,
    but does not implement execution semantics (stall/fix/route).
    """

    def __init__(self, enabled: bool = None) -> None:
        self._enabled = enabled if enabled is not None else RCX_BYTECODE_V0_ENABLED

        # State model
        self.mu_store: Dict[int, Any] = {}
        self.buckets: Dict[str, List] = {
            "r_null": [],
            "r_inf": [],
            "r_a": [],
            "lobes": [],
            "sink": [],
        }
        self.cursor = Cursor()
        self.artifacts = Artifacts()

        # Internal state for opcode execution (exposed via properties for testing)
        self._current_event: Optional[Dict[str, Any]] = None
        self._canonical_event: Optional[Dict[str, Any]] = None
        self._instructions: List[Instruction] = []

    @property
    def is_enabled(self) -> bool:
        """True if bytecode validation is enabled."""
        return self._enabled

    @property
    def current_event(self) -> Optional[Dict[str, Any]]:
        """Current loaded event (for testing/debugging)."""
        return self._current_event

    @current_event.setter
    def current_event(self, value: Optional[Dict[str, Any]]) -> None:
        """Set current event (for testing opcode sequences)."""
        self._current_event = value

    @property
    def canonical_event(self) -> Optional[Dict[str, Any]]:
        """Current canonical event (for testing/debugging)."""
        return self._canonical_event

    @canonical_event.setter
    def canonical_event(self, value: Optional[Dict[str, Any]]) -> None:
        """Set canonical event (for testing opcode sequences)."""
        self._canonical_event = value

    @property
    def instructions(self) -> List[Instruction]:
        """List of executed instructions (for debugging/golden comparison)."""
        return list(self._instructions)

    def reset(self) -> None:
        """Reset VM to initial state."""
        self.mu_store = {}
        self.buckets = {k: [] for k in self.buckets}
        self.cursor = Cursor()
        self.artifacts = Artifacts()
        self._current_event = None
        self._canonical_event = None
        self._instructions = []

    # --- Opcode Execution ---

    def _record(self, opcode: Opcode, **args) -> None:
        """Record an instruction execution."""
        self._instructions.append(Instruction(opcode, args))

    def op_init(self) -> None:
        """INIT: Initialize VM state."""
        self.cursor.i = 0
        self.cursor.phase = Phase.START
        self._record(Opcode.INIT)

    def op_load_event(self, ev: Dict[str, Any]) -> None:
        """LOAD_EVENT: Parse and validate event against v1 schema."""
        # Validate required fields
        v = ev.get("v")
        if v not in (1, 2):
            raise BytecodeVMError(f"Invalid event.v: {v!r} (must be 1 or 2)")

        typ = ev.get("type")
        if not isinstance(typ, str) or not typ.strip():
            raise BytecodeVMError(f"Invalid event.type: {typ!r}")

        i = ev.get("i")
        if not isinstance(i, int) or i < 0:
            raise BytecodeVMError(f"Invalid event.i: {i!r}")

        self._current_event = ev
        self._record(Opcode.LOAD_EVENT, event_type=typ, index=i)

    def op_canon_event(self) -> None:
        """CANON_EVENT: Canonicalize loaded event."""
        if self._current_event is None:
            raise BytecodeVMError("CANON_EVENT: No event loaded")

        self._canonical_event = canon_event(self._current_event)
        self._record(Opcode.CANON_EVENT)

    def op_store_mu(self) -> None:
        """STORE_MU: Store mu payload at current cursor.i."""
        if self._canonical_event is None:
            raise BytecodeVMError("STORE_MU: No canonical event")

        mu = self._canonical_event.get("mu")
        if mu is not None:
            self.mu_store[self.cursor.i] = mu

        self._record(Opcode.STORE_MU, index=self.cursor.i)

    def op_emit_canon(self) -> None:
        """EMIT_CANON: Append canonical JSON line to artifacts."""
        if self._canonical_event is None:
            raise BytecodeVMError("EMIT_CANON: No canonical event")

        line = json.dumps(
            self._canonical_event,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=False,
        )

        if self.artifacts.canon_out:
            self.artifacts.canon_out += "\n"
        self.artifacts.canon_out += line

        self._record(Opcode.EMIT_CANON)

    def op_advance(self) -> None:
        """ADVANCE: Increment cursor.i."""
        self.cursor.i += 1
        self._record(Opcode.ADVANCE, new_index=self.cursor.i)

    def op_set_phase(self, phase: Phase) -> None:
        """SET_PHASE: Set cursor.phase."""
        self.cursor.phase = phase
        self._record(Opcode.SET_PHASE, phase=phase.name)

    def op_assert_contiguous(self, expected: int) -> None:
        """ASSERT_CONTIGUOUS: Fail if cursor.i != expected."""
        if self._current_event is None:
            raise BytecodeVMError("ASSERT_CONTIGUOUS: No event loaded")

        actual = self._current_event.get("i")
        if actual != expected:
            raise BytecodeVMError(
                f"Contiguity violation at index {self.cursor.i}: "
                f"expected i={expected}, got i={actual}"
            )

        self._record(Opcode.ASSERT_CONTIGUOUS, expected=expected, actual=actual)

    def op_halt_ok(self) -> None:
        """HALT_OK: Set phase to END, return success."""
        self.cursor.phase = Phase.END
        self._record(Opcode.HALT_OK)

    def op_halt_err(self, msg: str) -> None:
        """HALT_ERR: Set phase to HALTED, record error."""
        self.cursor.phase = Phase.HALTED
        self.artifacts.error = msg
        self._record(Opcode.HALT_ERR, message=msg)

    # --- Event Type Mapping ---

    def _execute_trace_start(self, ev: Dict[str, Any]) -> None:
        """Execute opcode sequence for trace.start event."""
        # Precondition: phase == START, i == 0
        if self.cursor.phase != Phase.START:
            raise BytecodeVMError(
                f"trace.start: expected phase START, got {self.cursor.phase.name}"
            )

        self.op_load_event(ev)
        self.op_assert_contiguous(0)
        self.op_canon_event()
        self.op_store_mu()
        self.op_emit_canon()
        self.op_set_phase(Phase.RUNNING)
        self.op_advance()

    def _execute_step(self, ev: Dict[str, Any]) -> None:
        """Execute opcode sequence for step event."""
        # Precondition: phase == RUNNING, i > 0
        if self.cursor.phase != Phase.RUNNING:
            raise BytecodeVMError(
                f"step: expected phase RUNNING, got {self.cursor.phase.name}"
            )

        self.op_load_event(ev)
        self.op_assert_contiguous(self.cursor.i)
        self.op_canon_event()
        self.op_store_mu()
        self.op_emit_canon()
        self.op_advance()

    def _execute_trace_end(self, ev: Dict[str, Any]) -> None:
        """Execute opcode sequence for trace.end event."""
        # Precondition: phase == RUNNING
        if self.cursor.phase != Phase.RUNNING:
            raise BytecodeVMError(
                f"trace.end: expected phase RUNNING, got {self.cursor.phase.name}"
            )

        self.op_load_event(ev)
        self.op_assert_contiguous(self.cursor.i)
        self.op_canon_event()
        self.op_store_mu()
        self.op_emit_canon()
        self.op_halt_ok()

    def execute_event(self, ev: Dict[str, Any]) -> None:
        """
        Execute a single trace event.

        Maps event type to opcode sequence per BytecodeMapping.v0.md section 5.
        """
        if not self._enabled:
            return

        # Validate schema first (before type mapping)
        v = ev.get("v")
        if v not in (1, 2):
            self.op_halt_err(f"Invalid event.v: {v!r}")
            raise BytecodeVMError(f"Invalid event.v: {v!r}")

        typ = ev.get("type")
        if not isinstance(typ, str) or not typ.strip():
            self.op_halt_err(f"Invalid event.type: {typ!r}")
            raise BytecodeVMError(f"Invalid event.type: {typ!r}")

        i = ev.get("i")
        if not isinstance(i, int) or i < 0:
            self.op_halt_err(f"Invalid event.i: {i!r}")
            raise BytecodeVMError(f"Invalid event.i: {i!r}")

        # Map event type to opcode sequence
        if typ == "trace.start":
            self._execute_trace_start(ev)
        elif typ == "step":
            self._execute_step(ev)
        elif typ == "trace.end":
            self._execute_trace_end(ev)
        else:
            # v1 unknown event type -> HALT_ERR
            # v2 observability events are allowed but not mapped
            if v == 1:
                self.op_halt_err(f"unmappable event type: {typ}")
                raise BytecodeVMError(f"unmappable event type: {typ}")
            # v2 events are debug-only, skip silently

    def run(self, events: List[Dict[str, Any]]) -> Tuple[bool, str]:
        """
        Run the VM on a sequence of events.

        Returns:
            (success: bool, output: str)
            - success: True if HALT_OK, False if HALT_ERR
            - output: canonical JSONL output or error message
        """
        if not self._enabled:
            # When disabled, just return empty success
            return True, ""

        self.reset()
        self.op_init()

        try:
            for ev in events:
                self.execute_event(ev)

                # Stop if halted
                if self.cursor.phase in (Phase.END, Phase.HALTED):
                    break

            # Check final state
            if self.cursor.phase == Phase.HALTED:
                return False, self.artifacts.error or "Unknown error"
            else:
                # END or RUNNING - both are valid
                # (RUNNING means incomplete trace, but still valid for replay)
                output = self.artifacts.canon_out
                if output and not output.endswith("\n"):
                    output += "\n"
                return True, output

        except BytecodeVMError as e:
            return False, str(e)

    def emit_bytecode(self, events: List[Dict[str, Any]]) -> List[str]:
        """
        Generate bytecode instruction sequence for events.

        Returns list of instruction strings for debugging/golden comparison.
        """
        # Run to populate instructions
        self.run(events)
        return [str(inst) for inst in self._instructions]


def validate_bytecode(events: List[Dict[str, Any]]) -> Tuple[bool, str]:
    """
    Validate a trace using the bytecode VM.

    Returns:
        (valid: bool, message: str)
    """
    vm = BytecodeVM(enabled=True)
    success, output = vm.run(events)

    if success:
        return True, "Bytecode validation passed"
    else:
        return False, f"Bytecode validation failed: {output}"


def bytecode_replay(events: List[Dict[str, Any]]) -> Tuple[bool, str, List[str]]:
    """
    Replay trace through bytecode VM, returning canonical output and instructions.

    Returns:
        (success: bool, canon_output: str, instructions: List[str])
    """
    vm = BytecodeVM(enabled=True)
    success, output = vm.run(events)
    instructions = [str(inst) for inst in vm.instructions]

    return success, output, instructions
