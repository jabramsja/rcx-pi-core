"""
Tests for RCX Bytecode VM v0.

Covers:
- Opcode unit tests (each of 10 v0 opcodes)
- Event mapping tests (trace.start, step, trace.end, unknown)
- Golden round-trip tests (v1 fixtures)
- Rejection tests (bad index, unknown type, schema violation, phase error)
- Reserved opcode guard tests
"""

import json
import pytest
from pathlib import Path

from rcx_pi.bytecode_vm import (
    BytecodeVM,
    BytecodeVMError,
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
    """Tests that reserved opcodes are blocked in v0."""

    def test_reserved_opcodes_defined(self):
        """Verify reserved opcodes are in the blocked set."""
        assert Opcode.STALL in RESERVED_OPCODES
        assert Opcode.FIX in RESERVED_OPCODES
        assert Opcode.ROUTE in RESERVED_OPCODES
        assert Opcode.CLOSE in RESERVED_OPCODES

    def test_reserved_opcodes_count(self):
        """Verify exactly 4 reserved opcodes."""
        assert len(RESERVED_OPCODES) == 4


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
