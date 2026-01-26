"""
RCX Bytecode VM v0/v1b - Replay + STALL/FIX/FIXED execution.

v0: Replay-only bytecode execution for v1 trace events.
v1a: Adds OP_STALL execution (stall declaration).
v1b: Adds OP_FIX/OP_FIXED execution (stall resolution).

Design docs:
- docs/BytecodeMapping.v0.md (replay)
- docs/BytecodeMapping.v1.md (execution)

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
    """VM execution phase (trace-level)."""
    START = auto()
    RUNNING = auto()
    END = auto()
    HALTED = auto()


class ExecutionStatus(Enum):
    """VM execution status (value-level, per BytecodeMapping.v1.md)."""
    ACTIVE = auto()    # Value is being reduced
    STALLED = auto()   # Pattern match failed, awaiting fix


class Opcode(Enum):
    """
    Bytecode opcodes for v0 replay + v1b execution.

    v0 opcodes (implemented):
    - INIT through HALT_ERR: Core replay operations

    v1a opcodes (implemented):
    - STALL: Execution stall (pattern match failed)

    v1b opcodes (implemented):
    - FIX: Declare fix target (optional, must match current value_hash)
    - FIXED: Complete fix (value transition, return to ACTIVE)

    Reserved opcodes (NOT implemented until v1c+):
    - ROUTE, CLOSE: Blocked until explicit promotion

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

    # Execution opcodes (v1+)
    # These are defined for documentation and now implemented
    STALL = auto()   # v1a: Declare no reduction available
    FIX = auto()     # v1b: Declare fix target (optional)
    FIXED = auto()   # v1b: Complete fix with value transition

    # Reserved opcodes (v1c+ only, blocked until promotion)
    ROUTE = auto()
    CLOSE = auto()

    # Debug opcodes (v2 observability, no state change)
    DBG_STALL = auto()
    DBG_APPLIED = auto()
    DBG_NORMAL = auto()


# Reserved opcodes that must not be executed until v1c+
# Note: STALL removed in v1a, FIX removed in v1b (now implemented)
RESERVED_OPCODES = frozenset([Opcode.ROUTE, Opcode.CLOSE])

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
    Bytecode VM for v0 replay + v1b execution.

    State model (per BytecodeMapping.v0.md section 3 + v1.md):
    - mu_store: Map from event index to mu payload
    - buckets: Routing state (declared but not modified in v0/v1b)
    - cursor: Current position and phase
    - artifacts: Output accumulator and error state

    v1 registers (per BytecodeMapping.v1.md):
    - RS: Execution status (ACTIVE or STALLED)
    - RP: Current pattern_id being matched
    - RH: Current value_hash
    - RF: Pending fix target hash (v1b, optional)

    v0 is replay-only. v1a adds OP_STALL. v1b adds OP_FIX/OP_FIXED.
    """

    def __init__(self, enabled: bool = None) -> None:
        self._enabled = enabled if enabled is not None else RCX_BYTECODE_V0_ENABLED

        # State model (v0)
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

        # v1 registers (per BytecodeMapping.v1.md)
        self._rs: ExecutionStatus = ExecutionStatus.ACTIVE  # RS: status
        self._rp: Optional[str] = None  # RP: pattern_id
        self._rh: Optional[str] = None  # RH: value_hash
        self._rf: Optional[str] = None  # RF: pending_fix_target_hash (v1b)

        # Second Independent Encounter tracking (for closure detection)
        self._stall_memory: Dict[str, str] = {}  # pattern_id -> value_hash
        self._closure_evidence: List[Dict[str, str]] = []

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

    # --- v1 Register Properties ---

    @property
    def execution_status(self) -> ExecutionStatus:
        """RS register: Current execution status (ACTIVE or STALLED)."""
        return self._rs

    @property
    def pattern_id(self) -> Optional[str]:
        """RP register: Current pattern_id being matched."""
        return self._rp

    @property
    def value_hash(self) -> Optional[str]:
        """RH register: Current value_hash."""
        return self._rh

    @property
    def fix_target_hash(self) -> Optional[str]:
        """RF register: Pending fix target hash (v1b, set by OP_FIX)."""
        return self._rf

    @property
    def closure_evidence(self) -> List[Dict[str, str]]:
        """List of closure evidence detected via second independent encounter."""
        return list(self._closure_evidence)

    @property
    def has_closure(self) -> bool:
        """True if any closure evidence has been detected."""
        return len(self._closure_evidence) > 0

    def reset(self) -> None:
        """Reset VM to initial state."""
        # v0 state
        self.mu_store = {}
        self.buckets = {k: [] for k in self.buckets}  # AST_OK: infra
        self.cursor = Cursor()
        self.artifacts = Artifacts()
        self._current_event = None
        self._canonical_event = None
        self._instructions = []
        # v1 state
        self._rs = ExecutionStatus.ACTIVE
        self._rp = None
        self._rh = None
        self._rf = None  # v1b
        self._stall_memory = {}
        self._closure_evidence = []

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

    # --- v1 Execution Opcodes ---

    def op_stall(self, pattern_id: str, value_hash: str) -> bool:
        """
        OP_STALL: Declare no reduction is available for (value_hash, pattern_id).

        Per BytecodeMapping.v1.md:
        - Emits execution.stall with (value_hash=RH, pattern_id=RP)
        - Sets RS = STALLED
        - Constraint: Cannot stall while already STALLED (double-stall error)

        Second Independent Encounter (per IndependentEncounter.v0.md):
        - If same (value_hash, pattern_id) stalled before, closure is detected

        Returns:
            True if closure was detected (second independent encounter)
        """
        # Constraint: no double-stall
        if self._rs == ExecutionStatus.STALLED:
            raise BytecodeVMError(
                f"OP_STALL: Cannot stall while already STALLED (double-stall at pattern_id={pattern_id})"
            )

        # Set registers
        self._rp = pattern_id
        self._rh = value_hash
        self._rs = ExecutionStatus.STALLED

        # Check for second independent encounter (closure detection)
        closure_detected = self._check_second_independent_encounter(pattern_id, value_hash)

        # Record instruction
        self._record(Opcode.STALL, pattern_id=pattern_id, value_hash=value_hash)

        return closure_detected

    def _check_second_independent_encounter(self, pattern_id: str, value_hash: str) -> bool:
        """
        Check if this stall is a second independent encounter.

        Per IndependentEncounter.v0.md:
        - If stall_memory[pattern_id] == value_hash, this is second independent encounter
        - Otherwise, record stall_memory[pattern_id] = value_hash

        Returns:
            True if closure is detected
        """
        if pattern_id in self._stall_memory and self._stall_memory[pattern_id] == value_hash:
            # Second independent encounter detected
            self._closure_evidence.append({
                "value_hash": value_hash,
                "pattern_id": pattern_id,
                "reason": "second_independent_stall",
            })
            return True
        # Record this stall
        self._stall_memory[pattern_id] = value_hash
        return False

    def simulate_fix_for_test(self) -> None:
        """
        Test infrastructure: Simulate a FIX resolving a STALL without value change.

        Use this for testing second independent encounter detection where the
        value stays the same. For tests that need actual value transitions,
        use op_fixed() instead.

        NOTE: This does NOT clear stall_memory (per IndependentEncounter.v0.md,
        stall memory is only cleared on value transition, not on fix).
        """
        if self._rs != ExecutionStatus.STALLED:
            raise BytecodeVMError(
                "simulate_fix_for_test: Cannot fix when not STALLED"
            )
        self._rs = ExecutionStatus.ACTIVE

    # --- v1b Execution Opcodes ---

    def op_fix(self, target_hash: str) -> None:
        """
        OP_FIX: Declare intent to fix a stalled value.

        Per BytecodeMapping.v1.md:
        - Allowed only when RS == STALLED
        - Requires target_hash == RH (must match current value)
        - Sets RF = target_hash
        - Emits execution.fix(target_hash=RF)
        - Does NOT change R0/RH

        This is an optional step before OP_FIXED. The VM can go directly
        from STALL to FIXED without OP_FIX.
        """
        # Constraint: must be stalled
        if self._rs != ExecutionStatus.STALLED:
            raise BytecodeVMError(
                f"OP_FIX: Cannot fix when not STALLED (status={self._rs.name})"
            )

        # Constraint: target_hash must match current RH
        if target_hash != self._rh:
            raise BytecodeVMError(
                f"OP_FIX: target_hash mismatch (target={target_hash}, RH={self._rh})"
            )

        # Set RF register
        self._rf = target_hash

        # Record instruction
        self._record(Opcode.FIX, target_hash=target_hash)

    def op_fixed(self, after_value: Any, after_hash: str) -> None:
        """
        OP_FIXED: Complete a fix by transitioning to a new value.

        Per BytecodeMapping.v1.md:
        - Allowed only when RS == STALLED
        - If RF is set, it must equal RH (validated by OP_FIX)
        - Computes after_hash from after_value (caller provides both)
        - Emits execution.fixed(before_hash=RH, after_hash=after_hash)
        - Sets R0 = after_value; RH = after_hash
        - Sets RS = ACTIVE
        - Clears RF
        - Clears stall_memory (value transition per IndependentEncounter.v0.md)

        Note: The after_hash is provided by the caller to maintain determinism.
        The VM trusts that after_hash is correctly computed from after_value.
        """
        # Constraint: must be stalled
        if self._rs != ExecutionStatus.STALLED:
            raise BytecodeVMError(
                f"OP_FIXED: Cannot complete fix when not STALLED (status={self._rs.name})"
            )

        # If RF is set (OP_FIX was called), verify it matches RH
        if self._rf is not None and self._rf != self._rh:
            raise BytecodeVMError(
                f"OP_FIXED: RF/RH mismatch (RF={self._rf}, RH={self._rh})"
            )

        # Capture before_hash
        before_hash = self._rh

        # Update registers
        # Note: R0 (value) is conceptual - we track RH (hash) for validation
        self._rh = after_hash
        self._rs = ExecutionStatus.ACTIVE
        self._rf = None  # Clear fix target

        # Clear stall_memory on value transition (per IndependentEncounter.v0.md)
        self._stall_memory.clear()

        # Record instruction
        self._record(Opcode.FIXED, before_hash=before_hash, after_hash=after_hash)

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
        return [str(inst) for inst in self._instructions]  # AST_OK: infra


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
    instructions = [str(inst) for inst in vm.instructions]  # AST_OK: infra

    return success, output, instructions
