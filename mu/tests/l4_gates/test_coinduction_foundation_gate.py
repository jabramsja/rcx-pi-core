"""Foundation gate for the bounded Coinduction v0 specification.

This test intentionally does not execute production coinductive semantics. It
locks the first falsifiable docs criteria from the
coinduction-non-termination-as-structure wave: the spec is discoverable,
bounded, structural-data-first, explicit about observation and guardedness
obligations, and explicit about proof limits.
"""

from __future__ import annotations

import json
import re

import pytest

from tests.repo_root import REPO_ROOT


WAVE_ID = "coinduction-non-termination-as-structure-2026-06-27"
SPEC_PATH = REPO_ROOT / "mu" / "docs" / "core" / "Coinduction.v0.md"
TEST_PATH = "mu/tests/l4_gates/test_coinduction_foundation_gate.py"
DOCS_TEST_PATH = "mu/tests/docs/test_coinduction_foundation_gate.py"
CONFIG_PATH = (
    REPO_ROOT
    / "reports"
    / "control_plane"
    / "coinduction-non-termination-as-structure-2026-06-27_wave_config.json"
)
PACKET_REF = (
    "reports/control_plane/"
    "coinduction-non-termination-as-structure-2026-06-27_2026-06-27.md"
)
PACKET_PATH = REPO_ROOT / PACKET_REF
TASKS_PATH = REPO_ROOT / "TASKS.md"


def _spec_text() -> str:
    assert SPEC_PATH.exists(), "Coinduction.v0.md must exist in mu/docs/core/"
    return SPEC_PATH.read_text(encoding="utf-8")


def _normalized_spec_text() -> str:
    return " ".join(_spec_text().split())


# Active structural-program list authority in TASKS.md. The program is a
# numbered list of bolded entries ("N. **Item** ...") terminated by the
# "**DROPPED (do not pursue):**" marker line. A bolded entry PERSISTS through
# the queued -> in-flight -> landed transition (siblings already read
# "**Recursive ordinals** ... LANDED" and "**W-types / inductive types** ...
# LANDED"), so a membership check on the bolded entry is robust to queue-truth
# rephrasing -- unlike the old narrative position sentence that pinned
# Coinduction's exact queue slot, which any rephrase of that single TASKS.md
# sentence would break, stranding waves.
_PROGRAM_ENTRY_RE = re.compile(r"^[ \t]*\d+\.[ \t]+\*\*", re.MULTILINE)
_DROPPED_MARKER = "**DROPPED (do not pursue):**"


def _active_program_region(tasks_text: str) -> str:
    """Return the active structural-program slice of TASKS.md.

    The slice runs from the first numbered bolded program entry
    (``N. **Item** ...``) up to, but excluding, the
    ``**DROPPED (do not pursue):**`` terminator line.

    Fails closed on purpose: if the program list or its terminator cannot be
    located, this raises ``AssertionError`` instead of returning the whole file.
    A whole-file fallback would let a historical/frozen tracker-note mention
    (lowercase 'coinduction' at the bottom of TASKS.md) satisfy a membership
    check even after Coinduction was dropped from the active program, making the
    gate vacuous. The bounded region keeps the gate protective.
    """
    start = _PROGRAM_ENTRY_RE.search(tasks_text)
    assert start is not None, (
        "active structural-program list (N. **Item** ...) not found in TASKS.md"
    )
    end = tasks_text.find(_DROPPED_MARKER, start.start())
    assert end != -1, (
        "active-program terminator '**DROPPED (do not pursue):**' not found "
        "after the program list in TASKS.md"
    )
    region = tasks_text[start.start():end]
    assert region.strip(), "active structural-program region is empty"
    return region


def test_coinduction_doc_has_governed_header_and_grounding_gate():
    text = _spec_text()

    assert "DOC_STATUS" in text[:400]
    assert "TYPE: REFERENCE" in text[:400]
    assert "LAST_VERIFIED: 2026-06-27" in text[:400]
    assert f"GROUNDING_TESTS: {TEST_PATH}" in text[:500]


def test_coinduction_doc_is_discoverable_from_wave_authority():
    text = _spec_text()
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    packet_text = PACKET_PATH.read_text(encoding="utf-8")
    tasks_text = TASKS_PATH.read_text(encoding="utf-8")

    assert config["wave_id"] == WAVE_ID
    assert config["date"] == "2026-06-27"
    assert config["wave_class"] == "L4_ENABLER"
    assert config["task_id"] == "[NEXT-CODEX-POST-REDTEAM]"
    assert config["target_gate_id"] == "G8"
    assert config["tracked_packet"] == PACKET_REF
    assert "workload_target" not in config
    assert "host_semantics_delta_before" not in config
    assert "host_semantics_delta_after" not in config
    assert "mu/docs/core/Coinduction.v0.md" in config["structural_artifact_ref"]
    assert TEST_PATH in config["structural_artifact_ref"]
    assert DOCS_TEST_PATH in config["structural_artifact_ref"]
    assert "--wave-class L4_ENABLER" in config["evidence_command"]
    assert PACKET_REF in tasks_text
    assert TEST_PATH in tasks_text
    assert DOCS_TEST_PATH in tasks_text
    assert WAVE_ID in tasks_text
    assert "Class: L4_ENABLER" in tasks_text
    # Verify Coinduction/Fixpoint/Optimization are durable bolded entries in the
    # bounded active-program region, rather than pinning the brittle co-located
    # queue-position sentence (which named Coinduction's exact slot, Fixpoint's
    # order, and Optimization as last). The region bound keeps the check
    # non-vacuous: a lowercase mention in a historical/frozen tracker note below
    # the program list cannot satisfy it (see the negative-case test below).
    program_region = _active_program_region(tasks_text)
    assert "**Coinduction**" in program_region  # QUEUE_PHRASE_ROBUST
    assert "**Fixpoint**" in program_region  # QUEUE_PHRASE_ROBUST
    assert "**Optimization**" in program_region  # QUEUE_PHRASE_ROBUST
    assert any(  # QUEUE_PHRASE_ROBUST
        "**Optimization**" in entry
        and ("LAST" in entry or "out of scope" in entry.lower())
        for entry in program_region.splitlines()
    ), "Optimization program entry must remain annotated LAST / out of scope"
    assert "mu/docs/core/Coinduction.v0.md" in packet_text
    assert TEST_PATH in packet_text
    assert DOCS_TEST_PATH in packet_text
    assert "Coinduction.v0.md exists as a bounded design/spec" in packet_text
    assert "Optimization remains out of scope and LAST in TASKS.md." in packet_text
    assert "First Foundation Gate Criteria" in text


def test_coinduction_gate_fails_when_dropped_from_active_program():
    """Non-vacuity + fail-closed lock for the QUEUE_PHRASE_ROBUST check.

    Dropping the bolded ``**Coinduction**`` entry from the active-program region
    must make the membership assert fail, even though lowercase 'coinduction'
    mentions survive elsewhere in TASKS.md (the WAVE_ID, packet refs, narrative
    sentences, and historical tracker notes). This proves the check is
    region-bounded rather than a whole-file token scan, and that the region
    helper fails closed when its boundaries cannot be located -- so the gate can
    never silently degrade into a vacuous substring test.
    """
    tasks_text = TASKS_PATH.read_text(encoding="utf-8")

    # Sanity: the live file has the durable bolded entry inside the region.
    region = _active_program_region(tasks_text)
    assert "**Coinduction**" in region  # QUEUE_PHRASE_ROBUST

    # Drop the bolded entry from the active-program region ONLY. Lowercase
    # 'coinduction' mentions elsewhere in TASKS.md are intentionally preserved.
    mutated = tasks_text.replace(
        region, region.replace("**Coinduction**", "**(dropped)**")
    )
    assert "coinduction" in mutated.lower()  # a bare token scan would still pass

    mutated_region = _active_program_region(mutated)
    with pytest.raises(AssertionError):  # QUEUE_PHRASE_ROBUST
        assert "**Coinduction**" in mutated_region

    # The region helper itself fails closed when the program list or the
    # "**DROPPED (do not pursue):**" terminator cannot be located, so the check
    # never falls back to scanning the whole file.
    with pytest.raises(AssertionError):
        _active_program_region(mutated.replace(_DROPPED_MARKER, "(no terminator)"))
    with pytest.raises(AssertionError):
        _active_program_region("no numbered bolded program entries present")


def test_coinduction_spec_defines_structural_representation_boundary():
    text = _spec_text()
    normalized = _normalized_spec_text()

    required = [
        "not a host coroutine API",
        "not a host iterator API",
        "not a host async API",
        "not a host async loop model",
        "not a host process model",
        "not a host scheduler authority",
        "not a host liveness oracle",
        'co_trace        ::= {"_co_trace":',
        'observation_node ::= {"_co_observation":',
        'guarded_step    ::= {"_co_guarded_step":',
        'trace_prefix    ::= {"_co_prefix": null}',
        'observation_window ::= {"_co_window":',
        "do not require host generators, host coroutine frames",
        "does not authorize production coinductive runtime semantics",
    ]
    for phrase in required:
        assert phrase in normalized or phrase in text


def test_coinduction_spec_binds_observation_guardedness_and_windows():
    text = _spec_text()
    normalized = _normalized_spec_text()

    required = [
        "An observation node carries a structural label",
        "A guarded step exposes at least one observation",
        "productive trace prefix",
        "finite observation window",
        "An open tail is permitted only as an obligation marker",
        "Observation equivalence is a later proof obligation",
        "not Python generator semantics",
        "host scheduler semantics",
        "Guarded exposure",
        "Productive prefix extraction",
        "Finite observation windows",
        "Observation-equivalence obligations",
        "Bisimulation obligations",
        "Fail-closed malformed traces",
    ]
    for phrase in required:
        assert phrase in normalized or phrase in text


def test_coinduction_spec_names_finite_examples():
    text = _spec_text()
    normalized = _normalized_spec_text()

    required = [
        "### Constant Stream Prefix",
        "ObsZero0",
        "ObsZero1",
        "StepZero0",
        "ZeroPrefix2",
        "same structural zero payload",
        "### Repeating Structural Transition",
        "ObsA",
        "ObsB",
        "TogglePrefix2",
        "two observed transitions in a finite window",
        "### Finite Observation Window",
        "ToggleWindow2",
        "not a host time slice",
    ]
    for phrase in required:
        assert phrase in normalized or phrase in text


def test_coinduction_spec_defers_later_queue_items_and_withholds_runtime_authority():
    text = _spec_text()
    normalized = _normalized_spec_text()

    forbidden_claims = [
        "production coinductive runtime semantics are authorized",
        "coinductive semantic closure is complete",
        "productivity checker closure is complete",
        "bisimulation closure is complete",
        "scheduler closure is complete",
        "stream runtime closure is complete",
        "self-hosting closure is complete",
        "fixpoint closure is complete",
        "optimization is authorized",
    ]
    for phrase in forbidden_claims:
        assert phrase not in text

    required_limits = [
        "This v0 does not prove or authorize",
        "production coinductive runtime semantics",
        "production guarded corecursor, productivity checker, bisimulation checker",
        "scheduler, stream runtime, corecursive evaluator",
        "guarded corecursion execution, observation-equivalence closure",
        "coinductive evaluator closure, fixpoint closure",
        "non-termination proof by running forever",
        "changes to runtime, substrate, seed, registry, projection, JavaScript parity",
        "pager/autoping, tmux, evaluator, parser, or execution semantics files",
        "host coroutine behavior, host iterator authority",
        "host async/event-loop authority, host process liveness authority",
        "host scheduler authority",
        "Fixpoint remains the next structural queue item after Coinduction",
        "Optimization remains LAST",
    ]
    for phrase in required_limits:
        assert phrase in normalized or phrase in text


def test_coinduction_spec_links_existing_architecture_without_expanding_scope():
    text = _spec_text()

    required = [
        "`MuType.v0.md` remains the base value contract",
        "`SelfHosting.v0.md` and `MetaCircularKernel.v0.md` remain the current",
        "`StructuralPurity.v0.md` remains the guardrail",
        "`NorthStarSemantics.v0.md` remains the semantic policy lock",
        "`OntologyPromotionContract.v0.md` remains the promotion discipline",
        "`L3SubstrateArchitecture.v0.md` remains the L3/L4 boundary reference",
    ]
    for phrase in required:
        assert phrase in text
