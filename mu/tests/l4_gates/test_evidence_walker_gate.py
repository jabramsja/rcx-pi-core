"""
L4 Gate: evidence_walker.v1.json proof-class verification.

Python and JavaScript both execute verified evidence_walker.v1.json projections
for ontology evidence collection. JS host traversal is limited to boundary
post-processing and malformed/cyclic fallback handling.

Usage:
    PYTHONHASHSEED=0 pytest tests/l4_gates/test_evidence_walker_gate.py -v
"""

from __future__ import annotations

import functools
import json
import subprocess

import pytest

from rcx_pi.selfhost.step_mu import (
    run_mu,  # SPEED_OK: boundary wrapper tested via run_mu
)
from rcx_pi.selfhost.seed_integrity import (
    load_verified_seed,
    get_seed_path,
    EXPECTED_PROJECTION_IDS,
    SEED_CHECKSUMS,
)
from tests.repo_root import REPO_ROOT


@functools.lru_cache(maxsize=1)
def _js_registry_snapshot() -> dict[str, dict[str, object]]:
    js_script = """
    const sl = require('./mu/host/js/core/seed_loader');
    console.log(JSON.stringify({
      SEED_REGISTRY_MANIFEST: sl.SEED_REGISTRY_MANIFEST,
      SEED_CHECKSUMS: sl.SEED_CHECKSUMS,
      EXPECTED_PROJECTION_IDS: sl.EXPECTED_PROJECTION_IDS,
      CORE_SEED_CHECKSUMS: sl.CORE_SEED_CHECKSUMS,
      CORE_SEED_PROJECTION_IDS: sl.CORE_SEED_PROJECTION_IDS,
    }));
    """
    proc = subprocess.run(
        ["node", "-e", js_script],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=10,
    )
    assert proc.returncode == 0, f"JS registry probe failed: {proc.stderr}"
    return json.loads(proc.stdout)


# ---------------------------------------------------------------------------
# Gate Tests
# ---------------------------------------------------------------------------

class TestEvidenceWalkerSeedGate:
    """Gate: evidence_walker.v1.json loaded and verified in Python."""

    def test_seed_loads_with_4_projections(self):
        seed = load_verified_seed(get_seed_path("evidence_walker.v1.json"))
        assert len(seed["projections"]) == 4

    def test_projection_ids_registered(self):
        assert "evidence_walker.v1.json" in EXPECTED_PROJECTION_IDS
        assert len(EXPECTED_PROJECTION_IDS["evidence_walker.v1.json"]) == 4

    def test_checksum_registered(self):
        assert "evidence_walker.v1.json" in SEED_CHECKSUMS


class TestEvidenceWalkerJsRegistryGate:
    """Gate: JS core-locked registry includes evidence_walker.v1."""

    def test_js_seed_checksums_contains_evidence_walker(self):
        """JS SEED_CHECKSUMS must include manifest-registered evidence_walker.v1.json."""
        snapshot = _js_registry_snapshot()
        record = snapshot["SEED_REGISTRY_MANIFEST"]["seeds"]["evidence_walker.v1.json"]
        assert record["js_cli_registered"] is True
        assert record["js_core_locked"] is True
        assert "evidence_walker.v1.json" in snapshot["SEED_CHECKSUMS"]
        assert "evidence_walker.v1.json" in snapshot["CORE_SEED_CHECKSUMS"]
        py_checksum = SEED_CHECKSUMS["evidence_walker.v1.json"]
        js_checksum = snapshot["SEED_CHECKSUMS"]["evidence_walker.v1.json"]
        js_core_checksum = snapshot["CORE_SEED_CHECKSUMS"]["evidence_walker.v1.json"]
        assert js_checksum == py_checksum, (
            f"JS/Python checksum mismatch: JS={js_checksum} Python={py_checksum}"
        )
        assert js_core_checksum == py_checksum, (
            f"JS core/Python checksum mismatch: JS={js_core_checksum} Python={py_checksum}"
        )

    def test_js_projection_ids_contains_evidence_walker(self):
        """JS EXPECTED_PROJECTION_IDS must include manifest-registered evidence_walker.v1.json."""
        snapshot = _js_registry_snapshot()
        assert "evidence_walker.v1.json" in snapshot["EXPECTED_PROJECTION_IDS"]
        assert "evidence_walker.v1.json" in snapshot["CORE_SEED_PROJECTION_IDS"]
        py_ids = EXPECTED_PROJECTION_IDS["evidence_walker.v1.json"]
        js_ids = snapshot["EXPECTED_PROJECTION_IDS"]["evidence_walker.v1.json"]
        js_core_ids = snapshot["CORE_SEED_PROJECTION_IDS"]["evidence_walker.v1.json"]
        assert js_ids == py_ids
        assert js_core_ids == py_ids

    def test_js_core_verified_loads_evidence_walker(self):
        """JS core loadVerifiedSeed must accept evidence_walker.v1.json."""
        js_script = """
        const sl = require('./mu/host/js/core/seed_loader');
        const seed = sl.loadVerifiedSeed('evidence_walker.v1.json', 'utilities');
        process.stdout.write(JSON.stringify(seed.projections.map(p => p.id)));
        """
        proc = subprocess.run(
            ["node", "-e", js_script],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=10,
        )
        assert proc.returncode == 0, f"JS core seed load failed: {proc.stderr}"
        assert json.loads(proc.stdout) == EXPECTED_PROJECTION_IDS["evidence_walker.v1.json"]

    def test_js_collect_ontology_evidence_executes_verified_walker_projection(self):
        """A monkeypatched walker projection must control JS collection output."""
        js_script = """
        const muContainers = require('./mu/host/js/core/container_factory');
        function trustMu(value) {
          if (Array.isArray(value)) return muContainers.list(value.map(trustMu));
          if (value !== null && typeof value === 'object') {
            return muContainers.record(Object.keys(value).map(key => [key, trustMu(value[key])]));
          }
          return value;
        }
        const seedLoader = require('./mu/host/js/core/seed_loader');
        const originalLoad = seedLoader.loadVerifiedSeed;
        seedLoader.loadVerifiedSeed = function(seedName, subdir) {
          if (seedName === 'evidence_walker.v1.json') {
            return { projections: trustMu([{
              id: 'evidence.walk.test_override',
              pattern: { evidence_walk: { trace: { var: 'trace' } } },
              body: {
                evidence_done: {
                  collected: {
                    head: { projection: 'seed_override' },
                    tail: null
                  }
                }
              }
            }]) };
          }
          return originalLoad.call(this, seedName, subdir);
        };
        const pipeline = require('./mu/host/js/engine/pipeline');
        try {
          const result = trustMu({
            result: 'final',
            trace: { head: { projection: 'host_trace' }, tail: null },
            stall: false
          });
          const obs = pipeline.collectOntologyEvidence(result, 'run_trace');
          process.stdout.write(JSON.stringify({
            trace_len: obs.trace_len,
            projection_ids: obs.projection_ids
          }));
        } finally {
          seedLoader.loadVerifiedSeed = originalLoad;
        }
        """
        proc = subprocess.run(
            ["node", "-e", js_script],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=10,
        )
        assert proc.returncode == 0, f"JS walker projection probe failed: {proc.stderr}"
        assert json.loads(proc.stdout) == {
            "trace_len": 1,
            "projection_ids": ["seed_override"],
        }


@pytest.mark.slow
class TestEvidenceWalkerWiringGate:
    """Gate: evidence walker produces correct output for trace inputs."""

    def test_null_trace_produces_done(self):
        """Null trace → evidence_done with null collected."""
        projs = load_verified_seed(get_seed_path("evidence_walker.v1.json"))["projections"]
        wrapped = {"evidence_walk": {"trace": None}}
        result, _trace, _stall = run_mu(projs, wrapped, max_steps=20)
        assert isinstance(result, dict)
        assert "evidence_done" in result
        assert result["evidence_done"]["collected"] is None

    def test_trace_with_projection_collects_entry(self):
        """Trace entry with projection → raw entry collected."""
        projs = load_verified_seed(get_seed_path("evidence_walker.v1.json"))["projections"]
        trace = {"head": {"state": "a", "step": 0, "projection": "test.id"}, "tail": None}
        wrapped = {"evidence_walk": {"trace": trace}}
        result, _trace, _stall = run_mu(projs, wrapped, max_steps=20)
        assert "evidence_done" in result
        collected = result["evidence_done"]["collected"]
        # Mu runtime normalizes single-element {head,tail:null} to Python list
        if isinstance(collected, list):
            assert len(collected) == 1
            assert collected[0]["projection"] == "test.id"
        else:
            assert collected["head"]["projection"] == "test.id"

    def test_trace_without_projection_collects_entry(self):
        """Trace entry without projection → raw entry still collected."""
        projs = load_verified_seed(get_seed_path("evidence_walker.v1.json"))["projections"]
        trace = {"head": {"state": "a", "step": 0}, "tail": None}
        wrapped = {"evidence_walk": {"trace": trace}}
        result, _trace, _stall = run_mu(projs, wrapped, max_steps=20)
        assert "evidence_done" in result
        collected = result["evidence_done"]["collected"]
        if isinstance(collected, list):
            assert len(collected) == 1
            assert "projection" not in collected[0]
        else:
            assert "projection" not in collected["head"]

    def test_multi_entry_trace(self):
        """Multi-entry trace → all entries collected."""
        projs = load_verified_seed(get_seed_path("evidence_walker.v1.json"))["projections"]
        trace = {
            "head": {"state": "a", "step": 0, "projection": "p1"},
            "tail": {
                "head": {"state": "b", "step": 1},
                "tail": {
                    "head": {"state": "c", "step": 2, "projection": "p2"},
                    "tail": None,
                },
            },
        }
        wrapped = {"evidence_walk": {"trace": trace}}
        result, _trace, _stall = run_mu(projs, wrapped, max_steps=30)
        assert "evidence_done" in result
        collected = result["evidence_done"]["collected"]
        # Count entries
        count = 0
        node = collected
        if isinstance(node, list):
            count = len(node)
        else:
            while isinstance(node, dict) and "head" in node:
                count += 1
                node = node.get("tail")
        assert count == 3
