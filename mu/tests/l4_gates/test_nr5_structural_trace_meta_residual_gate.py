"""L4 gate for the NR-5 structural trace/meta-circular residual.

This gate binds the NR-5 residual repair to the runtime trace boundary: trace
step counters must remain StructuralNumbers values produced by the existing
StructuralNumbers ADD projection path, and matched projection IDs must still be
recorded in the run_mu_structural trace.
"""

from __future__ import annotations

import inspect

import pytest

from rcx_pi.selfhost import step_mu as step_mu_module
from rcx_pi.selfhost.step_mu import run_mu_structural  # SPEED_OK: bounded gate call
from tests.helpers.structural_numbers import SN_ONE, SN_ZERO

pytestmark = [pytest.mark.slow]


def _trace_entries(trace):
    entries = []
    node = trace
    while isinstance(node, dict) and "head" in node:
        entries.append(node["head"])
        node = node.get("tail")
    return entries


class TestNR5StructuralTraceMetaResidualGate:
    def test_trace_steps_are_structural_numbers_and_match_is_recorded(self):
        # SPEED_OK: two-step run_mu_structural call over one tiny projection.
        projections = [
            {
                "id": "nr5.tick",
                "pattern": {"tick": SN_ZERO},
                "body": {"tick": SN_ONE},
            }
        ]

        result = run_mu_structural(projections, {"tick": SN_ZERO}, max_steps=2)
        entries = _trace_entries(result["trace"])

        assert result["result"] == {"tick": SN_ONE}
        assert entries[0]["step"] == SN_ZERO
        assert entries[0]["projection"] == "nr5.tick"
        assert entries[1]["step"] == SN_ONE
        assert entries[1]["projection"] is None
        assert entries[2]["projection"] is None
        assert entries[2]["stall"] is True

    def test_run_mu_structural_keeps_structural_step_boundary_inline(self):
        source = inspect.getsource(step_mu_module.run_mu_structural)
        module_source = inspect.getsource(step_mu_module)
        assert "def _advance_structural_trace_step" not in module_source
        assert '"step": structural_step' in source
        assert '"step": next_structural_step' in source
        assert '"step": i' not in source
        assert '"step": i + 1' not in source

    def test_structural_step_boundary_uses_existing_add_projection_path(self):
        source = inspect.getsource(step_mu_module.run_mu_structural)
        assert "_STRUCTURAL_NUMBER_ADD_PROJECTIONS" in source
        assert "_step_trusted(_STRUCTURAL_NUMBER_ADD_PROJECTIONS, _sn_state)" in source
        assert "range(_SN_PROJECTION_STEP_LIMIT)" in source
        assert '{"_add": {"a": structural_step, "b": _SN_ONE}}' in source
        assert "next_structural_step = _sn_result" in source
        assert "StructuralNumbers ADD produced malformed numeral" in source
