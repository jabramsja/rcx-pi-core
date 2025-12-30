# test_api_named_programs.py

from rcx_pi import (
    num,
    list_from_py,
)
from rcx_pi.programs import succ_list_program
from rcx_pi.program_registry import register_program, clear_registry
from rcx_pi import run_named_list_program


def setup_function(_func):
    # Ensure a clean registry before each test if needed.
    clear_registry()


def test_run_succ_list_named_program():
    # Register the succ-list program under a stable name.
    prog = succ_list_program()
    register_program("succ-list", prog)

    # Call via the high-level named API.
    result = run_named_list_program("succ-list", [0, 1, 2, 3])
    assert result == [1, 2, 3, 4]


def test_run_named_program_unknown_raises():
    # With an empty registry, this should fail.
    try:
        run_named_list_program("does-not-exist", [0])
    except KeyError as e:
        assert "does-not-exist" in str(e)
    else:
        assert False, "Expected KeyError for unknown program name"