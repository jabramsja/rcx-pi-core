"""
Tests for RCX Bytecode VM v0/v1b.

Covers:
- Opcode unit tests (10 v0 opcodes + v1a OP_STALL + v1b OP_FIX/OP_FIXED)
- Event mapping tests (trace.start, step, trace.end, unknown)
- Golden round-trip tests (v1 fixtures)
- Rejection tests (bad index, unknown type, schema violation, phase error)
- Reserved opcode guard tests (ROUTE/CLOSE blocked, STALL/FIX/FIXED implemented)
- v1a OP_STALL tests (execution, closure detection)
- v1b OP_FIX/OP_FIXED tests (stall resolution, value transition)
"""

import json
import pytest
from pathlib import Path

from rcx_pi.bytecode_vm import (
    BytecodeVM,
    BytecodeVMError,
    ExecutionStatus,
    Opcode,
    Phase,
    RESERVED_OPCODES,
    validate_bytecode,
    bytecode_replay,
)
from rcx_pi.trace_canon import canon_jsonl


# --- Fixtures ---

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "traces"


def load_jsonl(path: Path) -> list:
    """Load JSONL file as list of events."""
    events = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


# --- Opcode Unit Tests ---


class TestOpcodeInit:
    """Tests for INIT opcode."""

    def test_init_sets_cursor_to_zero(self):
        vm = BytecodeVM(enabled=True)
        vm.cursor.i = 5  # Dirty state
        vm.cursor.phase = Phase.RUNNING
        vm.op_init()
        assert vm.cursor.i == 0
        assert vm.cursor.phase == Phase.START

    def test_init_records_instruction(self):
        vm = BytecodeVM(enabled=True)
        vm.op_init()
        assert len(vm.instructions) == 1
        assert vm.instructions[0].opcode == Opcode.INIT


class TestOpcodeLoadEvent:
    """Tests for LOAD_EVENT opcode."""

    def test_load_valid_v1_event(self):
        vm = BytecodeVM(enabled=True)
        ev = {"v": 1, "type": "trace.start", "i": 0}
        vm.op_load_event(ev)
        assert vm.current_event == ev

    def test_load_valid_v2_event(self):
        vm = BytecodeVM(enabled=True)
        ev = {"v": 2, "type": "execution.stall", "i": 0}
        vm.op_load_event(ev)
        assert vm.current_event == ev

    def test_load_invalid_version(self):
        vm = BytecodeVM(enabled=True)
        with pytest.raises(BytecodeVMError, match="Invalid event.v"):
            vm.op_load_event({"v": 3, "type": "step", "i": 0})

    def test_load_missing_type(self):
        vm = BytecodeVM(enabled=True)
        with pytest.raises(BytecodeVMError, match="Invalid event.type"):
            vm.op_load_event({"v": 1, "i": 0})

    def test_load_invalid_index(self):
        vm = BytecodeVM(enabled=True)
        with pytest.raises(BytecodeVMError, match="Invalid event.i"):
            vm.op_load_event({"v": 1, "type": "step", "i": -1})


class TestOpcodeCanonEvent:
    """Tests for CANON_EVENT opcode."""

    def test_canon_event_produces_canonical_form(self):
        vm = BytecodeVM(enabled=True)
        vm.current_event = {"v": 1, "type": "step", "i": 1, "mu": {"b": 2, "a": 1}}
        vm.op_canon_event()
        # Keys should be in canonical order, mu should be deep-sorted
        assert list(vm.canonical_event.keys()) == ["v", "type", "i", "mu"]
        assert list(vm.canonical_event["mu"].keys()) == ["a", "b"]

    def test_canon_event_fails_without_loaded_event(self):
        vm = BytecodeVM(enabled=True)
        with pytest.raises(BytecodeVMError, match="No event loaded"):
            vm.op_canon_event()


class TestOpcodeStoreMu:
    """Tests for STORE_MU opcode."""

    def test_store_mu_at_cursor_index(self):
        vm = BytecodeVM(enabled=True)
        vm.cursor.i = 3
        vm.canonical_event = {"v": 1, "type": "step", "i": 3, "mu": {"key": "value"}}
        vm.op_store_mu()
        assert vm.mu_store[3] == {"key": "value"}

    def test_store_mu_skips_if_no_mu(self):
        vm = BytecodeVM(enabled=True)
        vm.cursor.i = 0
        vm.canonical_event = {"v": 1, "type": "trace.start", "i": 0}
        vm.op_store_mu()
        assert 0 not in vm.mu_store

    def test_store_mu_fails_without_canonical_event(self):
        vm = BytecodeVM(enabled=True)
        with pytest.raises(BytecodeVMError, match="No canonical event"):
            vm.op_store_mu()


class TestOpcodeEmitCanon:
    """Tests for EMIT_CANON opcode."""

    def test_emit_canon_appends_json_line(self):
        vm = BytecodeVM(enabled=True)
        vm.canonical_event = {"v": 1, "type": "trace.start", "i": 0}
        vm.op_emit_canon()
        assert vm.artifacts.canon_out == '{"v":1,"type":"trace.start","i":0}'

    def test_emit_canon_appends_with_newline(self):
        vm = BytecodeVM(enabled=True)
        vm.canonical_event = {"v": 1, "type": "trace.start", "i": 0}
        vm.op_emit_canon()
        vm.canonical_event = {"v": 1, "type": "step", "i": 1}
        vm.op_emit_canon()
        lines = vm.artifacts.canon_out.split("\n")
        assert len(lines) == 2

    def test_emit_canon_fails_without_canonical_event(self):
        vm = BytecodeVM(enabled=True)
        with pytest.raises(BytecodeVMError, match="No canonical event"):
            vm.op_emit_canon()


class TestOpcodeAdvance:
    """Tests for ADVANCE opcode."""

    def test_advance_increments_cursor(self):
        vm = BytecodeVM(enabled=True)
        vm.cursor.i = 0
        vm.op_advance()
        assert vm.cursor.i == 1
        vm.op_advance()
        assert vm.cursor.i == 2


class TestOpcodeSetPhase:
    """Tests for SET_PHASE opcode."""

    def test_set_phase_to_running(self):
        vm = BytecodeVM(enabled=True)
        vm.cursor.phase = Phase.START
        vm.op_set_phase(Phase.RUNNING)
        assert vm.cursor.phase == Phase.RUNNING

    def test_set_phase_records_instruction(self):
        vm = BytecodeVM(enabled=True)
        vm.op_set_phase(Phase.END)
        assert vm.instructions[-1].opcode == Opcode.SET_PHASE
        assert vm.instructions[-1].args["phase"] == "END"


class TestOpcodeAssertContiguous:
    """Tests for ASSERT_CONTIGUOUS opcode."""

    def test_assert_contiguous_passes(self):
        vm = BytecodeVM(enabled=True)
        vm.current_event = {"v": 1, "type": "step", "i": 5}
        vm.op_assert_contiguous(5)  # Should not raise

    def test_assert_contiguous_fails_on_mismatch(self):
        vm = BytecodeVM(enabled=True)
        vm.current_event = {"v": 1, "type": "step", "i": 3}
        with pytest.raises(BytecodeVMError, match="Contiguity violation"):
            vm.op_assert_contiguous(5)


class TestOpcodeHaltOk:
    """Tests for HALT_OK opcode."""

    def test_halt_ok_sets_phase_to_end(self):
        vm = BytecodeVM(enabled=True)
        vm.cursor.phase = Phase.RUNNING
        vm.op_halt_ok()
        assert vm.cursor.phase == Phase.END


class TestOpcodeHaltErr:
    """Tests for HALT_ERR opcode."""

    def test_halt_err_sets_phase_and_error(self):
        vm = BytecodeVM(enabled=True)
        vm.op_halt_err("test error message")
        assert vm.cursor.phase == Phase.HALTED
        assert vm.artifacts.error == "test error message"


# --- Event Mapping Tests ---


class TestEventMappingTraceStart:
    """Tests for trace.start event mapping."""

    def test_trace_start_produces_7_instructions(self):
        vm = BytecodeVM(enabled=True)
        vm.op_init()
        ev = {"v": 1, "type": "trace.start", "i": 0}
        vm.execute_event(ev)
        # INIT + LOAD_EVENT + ASSERT_CONTIGUOUS + CANON_EVENT + STORE_MU + EMIT_CANON + SET_PHASE + ADVANCE
        # But INIT is called separately, so trace.start produces 7 instructions
        instructions = vm.instructions[1:]  # Skip INIT
        assert len(instructions) == 7
        assert instructions[0].opcode == Opcode.LOAD_EVENT
        assert instructions[1].opcode == Opcode.ASSERT_CONTIGUOUS
        assert instructions[2].opcode == Opcode.CANON_EVENT
        assert instructions[5].opcode == Opcode.SET_PHASE
        assert instructions[6].opcode == Opcode.ADVANCE

    def test_trace_start_requires_phase_start(self):
        vm = BytecodeVM(enabled=True)
        vm.cursor.phase = Phase.RUNNING
        with pytest.raises(BytecodeVMError, match="expected phase START"):
            vm.execute_event({"v": 1, "type": "trace.start", "i": 0})


class TestEventMappingStep:
    """Tests for step event mapping."""

    def test_step_produces_6_instructions(self):
        vm = BytecodeVM(enabled=True)
        vm.op_init()
        # First do trace.start
        vm.execute_event({"v": 1, "type": "trace.start", "i": 0})
        start_count = len(vm.instructions)

        # Now step
        vm.execute_event({"v": 1, "type": "step", "i": 1})
        step_instructions = vm.instructions[start_count:]
        assert len(step_instructions) == 6
        assert step_instructions[0].opcode == Opcode.LOAD_EVENT
        assert step_instructions[5].opcode == Opcode.ADVANCE

    def test_step_requires_phase_running(self):
        vm = BytecodeVM(enabled=True)
        vm.cursor.phase = Phase.START
        with pytest.raises(BytecodeVMError, match="expected phase RUNNING"):
            vm.execute_event({"v": 1, "type": "step", "i": 1})


class TestEventMappingTraceEnd:
    """Tests for trace.end event mapping."""

    def test_trace_end_produces_6_instructions(self):
        vm = BytecodeVM(enabled=True)
        vm.op_init()
        vm.execute_event({"v": 1, "type": "trace.start", "i": 0})
        start_count = len(vm.instructions)

        vm.execute_event({"v": 1, "type": "trace.end", "i": 1})
        end_instructions = vm.instructions[start_count:]
        assert len(end_instructions) == 6
        assert end_instructions[5].opcode == Opcode.HALT_OK

    def test_trace_end_sets_phase_to_end(self):
        vm = BytecodeVM(enabled=True)
        vm.op_init()
        vm.execute_event({"v": 1, "type": "trace.start", "i": 0})
        vm.execute_event({"v": 1, "type": "trace.end", "i": 1})
        assert vm.cursor.phase == Phase.END


class TestEventMappingUnknown:
    """Tests for unknown event type handling."""

    def test_unknown_v1_type_halts_with_error(self):
        vm = BytecodeVM(enabled=True)
        vm.op_init()
        vm.execute_event({"v": 1, "type": "trace.start", "i": 0})

        with pytest.raises(BytecodeVMError, match="unmappable event type"):
            vm.execute_event({"v": 1, "type": "unknown.event", "i": 1})

    def test_v2_observability_event_skipped(self):
        vm = BytecodeVM(enabled=True)
        vm.op_init()
        vm.execute_event({"v": 1, "type": "trace.start", "i": 0})

        # v2 events should be skipped, not cause error
        start_count = len(vm.instructions)
        vm.execute_event({"v": 2, "type": "execution.stall", "i": 1, "mu": {}})
        # No new instructions for v2 event
        assert len(vm.instructions) == start_count


# --- Golden Round-Trip Tests ---


class TestGoldenRoundTrip:
    """Tests that VM output matches canon_jsonl() exactly."""

    def test_minimal_v1_fixture(self):
        path = FIXTURES_DIR / "minimal.v1.jsonl"
        if not path.exists():
            pytest.skip(f"Fixture not found: {path}")

        events = load_jsonl(path)
        expected = canon_jsonl(events)

        success, output, _ = bytecode_replay(events)
        assert success, f"Bytecode replay failed: {output}"
        assert output == expected, f"Output mismatch:\nExpected:\n{expected}\nGot:\n{output}"

    def test_multi_v1_fixture(self):
        path = FIXTURES_DIR / "multi.v1.jsonl"
        if not path.exists():
            pytest.skip(f"Fixture not found: {path}")

        events = load_jsonl(path)
        expected = canon_jsonl(events)

        success, output, _ = bytecode_replay(events)
        assert success
        assert output == expected

    def test_nested_v1_fixture(self):
        path = FIXTURES_DIR / "nested.v1.jsonl"
        if not path.exists():
            pytest.skip(f"Fixture not found: {path}")

        events = load_jsonl(path)
        expected = canon_jsonl(events)

        success, output, _ = bytecode_replay(events)
        assert success
        assert output == expected

    def test_replay_freeze_v1_fixture(self):
        path = FIXTURES_DIR / "replay_freeze.v1.jsonl"
        if not path.exists():
            pytest.skip(f"Fixture not found: {path}")

        events = load_jsonl(path)
        expected = canon_jsonl(events)

        success, output, _ = bytecode_replay(events)
        assert success
        assert output == expected


# --- Rejection Tests ---


class TestRejection:
    """Tests for proper rejection of invalid inputs."""

    def test_reject_non_contiguous_index(self):
        events = [
            {"v": 1, "type": "trace.start", "i": 0},
            {"v": 1, "type": "step", "i": 2},  # Should be 1
        ]
        valid, msg = validate_bytecode(events)
        assert not valid
        assert "Contiguity violation" in msg

    def test_reject_unknown_v1_event_type(self):
        events = [
            {"v": 1, "type": "trace.start", "i": 0},
            {"v": 1, "type": "bad.event", "i": 1},
        ]
        valid, msg = validate_bytecode(events)
        assert not valid
        assert "unmappable event type" in msg

    def test_reject_invalid_schema_missing_type(self):
        events = [
            {"v": 1, "i": 0},  # Missing type
        ]
        valid, msg = validate_bytecode(events)
        assert not valid
        assert "Invalid event.type" in msg

    def test_reject_phase_error_trace_start_after_running(self):
        events = [
            {"v": 1, "type": "trace.start", "i": 0},
            {"v": 1, "type": "trace.start", "i": 1},  # Can't have second trace.start
        ]
        valid, msg = validate_bytecode(events)
        assert not valid
        assert "expected phase START" in msg


# --- Reserved Opcode Guard Tests ---


class TestReservedOpcodeGuard:
    """Tests that reserved opcodes are blocked (v1b: STALL/FIX/FIXED now implemented)."""

    def test_reserved_opcodes_defined(self):
        """Verify reserved opcodes are in the blocked set (v1b: only ROUTE/CLOSE)."""
        assert Opcode.STALL not in RESERVED_OPCODES  # v1a: implemented
        assert Opcode.FIX not in RESERVED_OPCODES     # v1b: implemented
        assert Opcode.ROUTE in RESERVED_OPCODES
        assert Opcode.CLOSE in RESERVED_OPCODES

    def test_reserved_opcodes_count(self):
        """Verify exactly 2 reserved opcodes (v1b: only ROUTE/CLOSE)."""
        assert len(RESERVED_OPCODES) == 2

    def test_stall_is_implemented(self):
        """Verify STALL opcode exists and is not reserved (v1a)."""
        assert hasattr(Opcode, "STALL")
        assert Opcode.STALL not in RESERVED_OPCODES

    def test_fix_fixed_are_implemented(self):
        """Verify FIX and FIXED opcodes exist and are not reserved (v1b)."""
        assert hasattr(Opcode, "FIX")
        assert hasattr(Opcode, "FIXED")
        assert Opcode.FIX not in RESERVED_OPCODES
        assert Opcode.FIXED not in RESERVED_OPCODES


# --- v1a OP_STALL Tests ---


class TestOpcodeStall:
    """Tests for OP_STALL opcode (v1a execution)."""

    def test_stall_sets_status_to_stalled(self):
        """OP_STALL sets RS register to STALLED."""
        vm = BytecodeVM(enabled=True)
        vm.op_init()
        assert vm.execution_status == ExecutionStatus.ACTIVE

        vm.op_stall(pattern_id="p1", value_hash="h1")
        assert vm.execution_status == ExecutionStatus.STALLED

    def test_stall_sets_registers(self):
        """OP_STALL sets RP and RH registers."""
        vm = BytecodeVM(enabled=True)
        vm.op_init()

        vm.op_stall(pattern_id="pattern_abc", value_hash="hash_xyz")
        assert vm.pattern_id == "pattern_abc"
        assert vm.value_hash == "hash_xyz"

    def test_stall_records_instruction(self):
        """OP_STALL records instruction with args."""
        vm = BytecodeVM(enabled=True)
        vm.op_init()
        vm.op_stall(pattern_id="p1", value_hash="h1")

        stall_insts = [i for i in vm.instructions if i.opcode == Opcode.STALL]
        assert len(stall_insts) == 1
        assert stall_insts[0].args["pattern_id"] == "p1"
        assert stall_insts[0].args["value_hash"] == "h1"

    def test_double_stall_raises_error(self):
        """Cannot stall while already STALLED (constraint from v1 doc)."""
        vm = BytecodeVM(enabled=True)
        vm.op_init()

        vm.op_stall(pattern_id="p1", value_hash="h1")
        assert vm.execution_status == ExecutionStatus.STALLED

        with pytest.raises(BytecodeVMError, match="double-stall"):
            vm.op_stall(pattern_id="p2", value_hash="h2")

    def test_stall_returns_false_on_first_encounter(self):
        """First stall at (pattern_id, value_hash) returns False (no closure)."""
        vm = BytecodeVM(enabled=True)
        vm.op_init()

        result = vm.op_stall(pattern_id="p1", value_hash="h1")
        assert result is False
        assert not vm.has_closure


class TestSecondIndependentEncounterVM:
    """Tests for closure detection via second independent encounter in VM."""

    def test_second_stall_same_pattern_value_detects_closure(self):
        """Second stall at same (pattern_id, value_hash) detects closure."""
        vm = BytecodeVM(enabled=True)
        vm.op_init()

        # First stall
        result1 = vm.op_stall(pattern_id="p1", value_hash="h1")
        assert result1 is False
        assert not vm.has_closure

        # Simulate a fix resolving the stall (placeholder for OP_FIX in v1b)
        vm.simulate_fix_for_test()

        # Second stall at same (p1, h1) - should detect closure
        result2 = vm.op_stall(pattern_id="p1", value_hash="h1")
        assert result2 is True
        assert vm.has_closure
        assert len(vm.closure_evidence) == 1
        assert vm.closure_evidence[0]["pattern_id"] == "p1"
        assert vm.closure_evidence[0]["value_hash"] == "h1"
        assert vm.closure_evidence[0]["reason"] == "second_independent_stall"

    def test_different_value_no_closure(self):
        """Stall at different value_hash does not detect closure."""
        vm = BytecodeVM(enabled=True)
        vm.op_init()

        vm.op_stall(pattern_id="p1", value_hash="h1")
        vm.simulate_fix_for_test()

        result = vm.op_stall(pattern_id="p1", value_hash="h2")  # Different hash
        assert result is False
        assert not vm.has_closure

    def test_different_pattern_no_closure(self):
        """Stall at different pattern_id does not detect closure."""
        vm = BytecodeVM(enabled=True)
        vm.op_init()

        vm.op_stall(pattern_id="p1", value_hash="h1")
        vm.simulate_fix_for_test()

        result = vm.op_stall(pattern_id="p2", value_hash="h1")  # Different pattern
        assert result is False
        assert not vm.has_closure

    def test_stall_memory_tracks_per_pattern(self):
        """Stall memory tracks value_hash per pattern_id."""
        vm = BytecodeVM(enabled=True)
        vm.op_init()

        # Stall at p1 with h1
        vm.op_stall(pattern_id="p1", value_hash="h1")
        vm.simulate_fix_for_test()

        # Stall at p2 with h2 (different pattern)
        vm.op_stall(pattern_id="p2", value_hash="h2")
        vm.simulate_fix_for_test()

        # Stall at p1 with h1 again - should detect closure for p1
        result = vm.op_stall(pattern_id="p1", value_hash="h1")
        assert result is True
        assert len(vm.closure_evidence) == 1
        assert vm.closure_evidence[0]["pattern_id"] == "p1"


class TestV1aRegisters:
    """Tests for v1a register properties."""

    def test_initial_execution_status_is_active(self):
        """Initial RS register is ACTIVE."""
        vm = BytecodeVM(enabled=True)
        assert vm.execution_status == ExecutionStatus.ACTIVE

    def test_initial_pattern_id_is_none(self):
        """Initial RP register is None."""
        vm = BytecodeVM(enabled=True)
        assert vm.pattern_id is None

    def test_initial_value_hash_is_none(self):
        """Initial RH register is None."""
        vm = BytecodeVM(enabled=True)
        assert vm.value_hash is None

    def test_reset_clears_v1a_state(self):
        """Reset clears v1a registers and stall memory."""
        vm = BytecodeVM(enabled=True)
        vm.op_init()
        vm.op_stall(pattern_id="p1", value_hash="h1")

        assert vm.execution_status == ExecutionStatus.STALLED
        assert vm.pattern_id == "p1"

        vm.reset()

        assert vm.execution_status == ExecutionStatus.ACTIVE
        assert vm.pattern_id is None
        assert vm.value_hash is None
        assert not vm.has_closure


# --- v1b OP_FIX Tests ---


class TestOpcodeFix:
    """Tests for OP_FIX opcode (v1b execution)."""

    def test_fix_requires_stalled_status(self):
        """OP_FIX raises error if not STALLED."""
        vm = BytecodeVM(enabled=True)
        vm.op_init()

        with pytest.raises(BytecodeVMError, match="Cannot fix when not STALLED"):
            vm.op_fix(target_hash="h1")

    def test_fix_requires_matching_target_hash(self):
        """OP_FIX raises error if target_hash != RH."""
        vm = BytecodeVM(enabled=True)
        vm.op_init()
        vm.op_stall(pattern_id="p1", value_hash="h1")

        with pytest.raises(BytecodeVMError, match="target_hash mismatch"):
            vm.op_fix(target_hash="wrong_hash")

    def test_fix_sets_rf_register(self):
        """OP_FIX sets RF register to target_hash."""
        vm = BytecodeVM(enabled=True)
        vm.op_init()
        vm.op_stall(pattern_id="p1", value_hash="h1")

        assert vm.fix_target_hash is None
        vm.op_fix(target_hash="h1")
        assert vm.fix_target_hash == "h1"

    def test_fix_does_not_change_status(self):
        """OP_FIX leaves RS as STALLED (doesn't complete fix)."""
        vm = BytecodeVM(enabled=True)
        vm.op_init()
        vm.op_stall(pattern_id="p1", value_hash="h1")
        vm.op_fix(target_hash="h1")

        assert vm.execution_status == ExecutionStatus.STALLED

    def test_fix_records_instruction(self):
        """OP_FIX records instruction with target_hash."""
        vm = BytecodeVM(enabled=True)
        vm.op_init()
        vm.op_stall(pattern_id="p1", value_hash="h1")
        vm.op_fix(target_hash="h1")

        fix_instr = [i for i in vm.instructions if i.opcode == Opcode.FIX]
        assert len(fix_instr) == 1
        assert fix_instr[0].args["target_hash"] == "h1"


class TestOpcodeFixed:
    """Tests for OP_FIXED opcode (v1b execution)."""

    def test_fixed_requires_stalled_status(self):
        """OP_FIXED raises error if not STALLED."""
        vm = BytecodeVM(enabled=True)
        vm.op_init()

        with pytest.raises(BytecodeVMError, match="Cannot complete fix when not STALLED"):
            vm.op_fixed(after_value={"new": "value"}, after_hash="h2")

    def test_fixed_sets_status_to_active(self):
        """OP_FIXED transitions RS from STALLED to ACTIVE."""
        vm = BytecodeVM(enabled=True)
        vm.op_init()
        vm.op_stall(pattern_id="p1", value_hash="h1")

        assert vm.execution_status == ExecutionStatus.STALLED
        vm.op_fixed(after_value={"new": "value"}, after_hash="h2")
        assert vm.execution_status == ExecutionStatus.ACTIVE

    def test_fixed_updates_value_hash(self):
        """OP_FIXED updates RH to after_hash."""
        vm = BytecodeVM(enabled=True)
        vm.op_init()
        vm.op_stall(pattern_id="p1", value_hash="h1")

        assert vm.value_hash == "h1"
        vm.op_fixed(after_value={"new": "value"}, after_hash="h2")
        assert vm.value_hash == "h2"

    def test_fixed_clears_rf_register(self):
        """OP_FIXED clears RF register."""
        vm = BytecodeVM(enabled=True)
        vm.op_init()
        vm.op_stall(pattern_id="p1", value_hash="h1")
        vm.op_fix(target_hash="h1")

        assert vm.fix_target_hash == "h1"
        vm.op_fixed(after_value={"new": "value"}, after_hash="h2")
        assert vm.fix_target_hash is None

    def test_fixed_clears_stall_memory(self):
        """OP_FIXED clears stall_memory (value transition per IndependentEncounter.v0.md)."""
        vm = BytecodeVM(enabled=True)
        vm.op_init()
        vm.op_stall(pattern_id="p1", value_hash="h1")

        # stall_memory should have p1 -> h1
        vm.op_fixed(after_value={"new": "value"}, after_hash="h2")

        # After FIXED, stall at same pattern should NOT detect closure
        # because stall_memory was cleared
        vm.op_stall(pattern_id="p1", value_hash="h2")
        vm.op_fixed(after_value={"another": "value"}, after_hash="h3")

        # Stall again - first encounter after value transition
        result = vm.op_stall(pattern_id="p1", value_hash="h3")
        assert result is False  # Not closure, first encounter at this value

    def test_fixed_without_prior_fix(self):
        """OP_FIXED works without OP_FIX (fix is optional)."""
        vm = BytecodeVM(enabled=True)
        vm.op_init()
        vm.op_stall(pattern_id="p1", value_hash="h1")

        # Go directly to FIXED without FIX
        vm.op_fixed(after_value={"new": "value"}, after_hash="h2")

        assert vm.execution_status == ExecutionStatus.ACTIVE
        assert vm.value_hash == "h2"

    def test_fixed_records_instruction(self):
        """OP_FIXED records instruction with before_hash and after_hash."""
        vm = BytecodeVM(enabled=True)
        vm.op_init()
        vm.op_stall(pattern_id="p1", value_hash="h1")
        vm.op_fixed(after_value={"new": "value"}, after_hash="h2")

        fixed_instr = [i for i in vm.instructions if i.opcode == Opcode.FIXED]
        assert len(fixed_instr) == 1
        assert fixed_instr[0].args["before_hash"] == "h1"
        assert fixed_instr[0].args["after_hash"] == "h2"


class TestFixFixedSequence:
    """Tests for OP_FIX + OP_FIXED sequence."""

    def test_full_stall_fix_fixed_cycle(self):
        """Complete STALL -> FIX -> FIXED cycle."""
        vm = BytecodeVM(enabled=True)
        vm.op_init()

        # STALL
        vm.op_stall(pattern_id="p1", value_hash="h1")
        assert vm.execution_status == ExecutionStatus.STALLED
        assert vm.value_hash == "h1"

        # FIX
        vm.op_fix(target_hash="h1")
        assert vm.execution_status == ExecutionStatus.STALLED
        assert vm.fix_target_hash == "h1"

        # FIXED
        vm.op_fixed(after_value={"fixed": "value"}, after_hash="h2")
        assert vm.execution_status == ExecutionStatus.ACTIVE
        assert vm.value_hash == "h2"
        assert vm.fix_target_hash is None

    def test_multiple_stall_fix_cycles(self):
        """Multiple STALL -> FIXED cycles in sequence."""
        vm = BytecodeVM(enabled=True)
        vm.op_init()

        # First cycle
        vm.op_stall(pattern_id="p1", value_hash="h1")
        vm.op_fixed(after_value={"v": 1}, after_hash="h2")
        assert vm.execution_status == ExecutionStatus.ACTIVE

        # Second cycle
        vm.op_stall(pattern_id="p2", value_hash="h2")
        vm.op_fix(target_hash="h2")
        vm.op_fixed(after_value={"v": 2}, after_hash="h3")
        assert vm.execution_status == ExecutionStatus.ACTIVE
        assert vm.value_hash == "h3"


class TestV1bRegisters:
    """Tests for v1b register properties."""

    def test_initial_fix_target_hash_is_none(self):
        """Initial RF register is None."""
        vm = BytecodeVM(enabled=True)
        assert vm.fix_target_hash is None

    def test_reset_clears_rf(self):
        """Reset clears RF register."""
        vm = BytecodeVM(enabled=True)
        vm.op_init()
        vm.op_stall(pattern_id="p1", value_hash="h1")
        vm.op_fix(target_hash="h1")

        assert vm.fix_target_hash == "h1"
        vm.reset()
        assert vm.fix_target_hash is None


# --- Determinism Tests ---


class TestDeterminism:
    """Tests that VM produces deterministic output."""

    def test_same_input_produces_same_output(self):
        events = [
            {"v": 1, "type": "trace.start", "i": 0, "t": "test"},
            {"v": 1, "type": "step", "i": 1, "mu": {"z": 3, "a": 1}},
            {"v": 1, "type": "trace.end", "i": 2},
        ]

        # Run twice
        success1, output1, inst1 = bytecode_replay(events)
        success2, output2, inst2 = bytecode_replay(events)

        assert success1 and success2
        assert output1 == output2
        assert inst1 == inst2

    def test_mu_key_order_is_deterministic(self):
        events = [
            {"v": 1, "type": "trace.start", "i": 0},
            {"v": 1, "type": "step", "i": 1, "mu": {"z": 1, "m": 2, "a": 3}},
            {"v": 1, "type": "trace.end", "i": 2},
        ]

        success, output, _ = bytecode_replay(events)
        assert success
        # mu keys should be sorted: a, m, z
        assert '"mu":{"a":3,"m":2,"z":1}' in output


# --- Instruction Recording Tests ---


class TestInstructionRecording:
    """Tests for instruction recording (for golden comparison)."""

    def test_instructions_are_recorded(self):
        events = [
            {"v": 1, "type": "trace.start", "i": 0},
            {"v": 1, "type": "trace.end", "i": 1},
        ]

        success, _, instructions = bytecode_replay(events)
        assert success
        assert len(instructions) > 0
        assert "INIT" in instructions[0]

    def test_instruction_string_format(self):
        vm = BytecodeVM(enabled=True)
        vm.op_init()
        vm.op_set_phase(Phase.RUNNING)

        insts = [str(i) for i in vm.instructions]
        assert insts[0] == "INIT"
        assert "SET_PHASE" in insts[1]
        assert "RUNNING" in insts[1]


# --- Integration Tests ---


class TestIntegration:
    """Integration tests for full replay flow."""

    def test_validate_bytecode_helper(self):
        events = [
            {"v": 1, "type": "trace.start", "i": 0},
            {"v": 1, "type": "trace.end", "i": 1},
        ]
        valid, msg = validate_bytecode(events)
        assert valid
        assert "passed" in msg.lower()

    def test_disabled_vm_returns_empty_success(self):
        vm = BytecodeVM(enabled=False)
        success, output = vm.run([{"v": 1, "type": "trace.start", "i": 0}])
        assert success
        assert output == ""

    def test_incomplete_trace_succeeds(self):
        """Incomplete traces are valid - we canonicalize what we have."""
        events = [
            {"v": 1, "type": "trace.start", "i": 0},
            {"v": 1, "type": "step", "i": 1},
            # Missing trace.end - but this is OK
        ]
        valid, msg = validate_bytecode(events)
        assert valid
        assert "passed" in msg.lower()
