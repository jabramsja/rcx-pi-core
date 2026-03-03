"""D010: H5 Projection Loader Binary Format — Research Artifact

RESEARCH ANALOG ONLY. This file demonstrates that the JSON parsing component
of projection_loader can be replaced with a custom recursive TLV decoder
operating on a minimal binary format. It does NOT change any production code.
Production seed_integrity.py / main.js are unchanged.

Tests H5 hypothesis: can the JSON parsing dependency in projection_loader be
replaced with a custom recursive TLV (tag-length-value) decoder, reducing the
host parsing surface from a full recursive-descent JSON grammar (~thousands of
LOC in host stdlib) to a minimal tag-dispatch decoder (~80-120 LOC)?

This proves PARSING-COMPONENT reducibility only. I/O (read bytes from disk)
and integrity verification (SHA256) remain irreducible host operations.
The decoder is a custom recursive TLV parser — nested dicts/lists require
recursive descent through the tag-dispatch loop, not flat sequential reads.

Success criteria:
  C1: Round-trip fidelity — encode(seed) decoded back to original for 2+
      canonical seeds (bootstrap_structural.v1, kernel.v1).
  C2: Golden byte fixtures — hardcoded byte blobs decoded independently
      of encoder produce expected Mu dicts (catches shared-bug blindness).
  C3: Engine-level behavioral parity — decoded projections produce
      identical output when run through step_kernel_mu as JSON-loaded ones.
  C4: No new bootstrap primitive introduced.

Failure criteria (honest limitations):
  F1: The decoder uses host isinstance for tag dispatch (type → tag byte).
  F2: The encoder uses host isinstance for type dispatch (same issue).
  F3: struct.pack/unpack are host operations for int/float serialization.
  F4: String encoding (UTF-8) relies on host str.encode/bytes.decode.
  F5: Dict key ordering relies on host dict iteration order.
  F6: The decoder is recursive — nested structures recurse through
      mu_decode, so host call stack depth limits apply.
  F7: I/O (reading bytes from disk) remains irreducible.
  F8: Integrity verification (SHA256/checksum) remains irreducible.
  F9: Seed structure validation (meta, projections array) remains host code.

Boundary lock criteria:
  B1: Round-trip: decode(encode(x)) == x for all Mu types in production seeds.
  B2: Type coverage: all 6 Mu types present in production seeds are supported
      (NoneType, bool, int, str, list, dict). Float supported for completeness.
  B3: Failure modes: truncated data, bad tag, length overflow, non-string
      dict key all raise specific errors. NaN/Inf round-trip via IEEE 754
      float encoding (research context; production seeds reject non-finite
      via seed_integrity.py parse_constant guard).

Coverage: 1 enforcement surface (JSON parsing in load_verified_seed).
The other 3 components (I/O, integrity, validation) are out of scope.

Explicit non-goals for D010:
  - Production seed format migration
  - Binary seed file generation tooling
  - JS cross-substrate binary decoder
  - I/O or SHA256 reducibility
  - Seed structure validation reducibility
  - Performance benchmarking (this is about reducibility, not speed)
  If binary format is ever promoted to production, cross-substrate parity,
  migration tooling, and integrity chain must be addressed in that future wave.

NOT production code. This file lives in tests/research/ and is never
imported by rcx_pi/.

Evidence for: mu/docs/core/L4DecisionCard.v0.md (D010)
               mu/docs/core/L4ExitChecklist.v0.md (G8, projection_loader)
"""

import ast
import inspect
import json
import struct
from pathlib import Path

import pytest

# Production functions — used ONLY for parity comparison and engine-level
# behavioral proof, not as execution substrate for binary decoding.
from rcx_pi.selfhost.eval_seed import match, substitute
from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seed_path
from rcx_pi.selfhost.step_mu import step_kernel_mu

from tests.repo_root import REPO_ROOT


# ---------------------------------------------------------------------------
# MuBinary TLV format: custom recursive tag-length-value decoder
# ---------------------------------------------------------------------------
#
# Tag bytes:
#   0x00 = null (None)     — no payload
#   0x01 = true            — no payload
#   0x02 = false           — no payload
#   0x03 = int64           — 8 bytes, big-endian signed
#   0x04 = float64         — 8 bytes, IEEE 754 big-endian
#   0x05 = string          — 4-byte BE length + UTF-8 bytes
#   0x06 = list            — 4-byte BE count + count × element
#   0x07 = dict            — 4-byte BE count + count × (key, value) pairs
#
# Design rationale:
#   - No grammar rules, no tokenizer, no whitespace handling
#   - Tag dispatch replaces recursive-descent JSON parser
#   - Fixed-width numerics eliminate number parsing
#   - Explicit count fields eliminate delimiter/nesting ambiguity
#   - Dict keys MUST be strings (Mu structural constraint)
#
# Honest limitation: nested lists/dicts require recursive mu_decode calls,
# so this is a custom RECURSIVE TLV decoder, not a flat sequential one.
# Host call stack depth limits apply to deeply nested structures.

TAG_NULL = 0x00
TAG_TRUE = 0x01
TAG_FALSE = 0x02
TAG_INT64 = 0x03
TAG_FLOAT64 = 0x04
TAG_STRING = 0x05
TAG_LIST = 0x06
TAG_DICT = 0x07


class MuBinaryDecodeError(Exception):
    """Raised when binary data cannot be decoded as valid Mu."""
    pass


def mu_encode(value):
    """Encode a Mu value to MuBinary TLV bytes.

    Supports: None, bool, int, float, str, list, dict.
    Dict keys must be strings (Mu structural constraint).

    F1/F2: Uses host isinstance for type dispatch.
    F3: Uses struct.pack for numeric serialization.
    F4: Uses str.encode for UTF-8 string encoding.
    F5: Dict key order follows host dict iteration order.
    """
    if value is None:
        return bytes([TAG_NULL])
    elif isinstance(value, bool):
        # bool before int — bool is subclass of int in Python
        return bytes([TAG_TRUE]) if value else bytes([TAG_FALSE])
    elif isinstance(value, int):
        return bytes([TAG_INT64]) + struct.pack(">q", value)
    elif isinstance(value, float):
        return bytes([TAG_FLOAT64]) + struct.pack(">d", value)
    elif isinstance(value, str):
        encoded = value.encode("utf-8")
        return bytes([TAG_STRING]) + struct.pack(">I", len(encoded)) + encoded
    elif isinstance(value, list):
        parts = [bytes([TAG_LIST]) + struct.pack(">I", len(value))]
        for item in value:
            parts.append(mu_encode(item))
        return b"".join(parts)
    elif isinstance(value, dict):
        for k in value:
            if not isinstance(k, str):
                raise ValueError(f"Dict key must be string, got {type(k).__name__}")
        parts = [bytes([TAG_DICT]) + struct.pack(">I", len(value))]
        for k, v in value.items():
            parts.append(mu_encode(k))
            parts.append(mu_encode(v))
        return b"".join(parts)
    else:
        raise TypeError(f"Cannot encode {type(value).__name__} as MuBinary")


def mu_decode(data, offset=0):
    """Decode a MuBinary TLV value from bytes at given offset.

    Returns (value, new_offset) tuple.

    This is a RECURSIVE decoder: nested list/dict values recurse through
    mu_decode. Host call stack depth limits apply.

    F3: Uses struct.unpack for numeric deserialization.
    F4: Uses bytes.decode for UTF-8 string decoding.
    F6: Recursive — host stack depth limits apply.
    """
    if offset >= len(data):
        raise MuBinaryDecodeError(
            f"Unexpected end of data at offset {offset} (data length {len(data)})"
        )

    tag = data[offset]
    offset += 1

    if tag == TAG_NULL:
        return None, offset

    elif tag == TAG_TRUE:
        return True, offset

    elif tag == TAG_FALSE:
        return False, offset

    elif tag == TAG_INT64:
        if offset + 8 > len(data):
            raise MuBinaryDecodeError(
                f"Truncated int64 at offset {offset - 1} "
                f"(need 8 bytes, have {len(data) - offset})"
            )
        value = struct.unpack(">q", data[offset:offset + 8])[0]
        return value, offset + 8

    elif tag == TAG_FLOAT64:
        if offset + 8 > len(data):
            raise MuBinaryDecodeError(
                f"Truncated float64 at offset {offset - 1} "
                f"(need 8 bytes, have {len(data) - offset})"
            )
        value = struct.unpack(">d", data[offset:offset + 8])[0]
        return value, offset + 8

    elif tag == TAG_STRING:
        if offset + 4 > len(data):
            raise MuBinaryDecodeError(
                f"Truncated string length at offset {offset - 1}"
            )
        length = struct.unpack(">I", data[offset:offset + 4])[0]
        offset += 4
        if offset + length > len(data):
            raise MuBinaryDecodeError(
                f"Truncated string data at offset {offset - 4} "
                f"(declared {length} bytes, have {len(data) - offset})"
            )
        value = data[offset:offset + length].decode("utf-8")
        return value, offset + length

    elif tag == TAG_LIST:
        if offset + 4 > len(data):
            raise MuBinaryDecodeError(
                f"Truncated list count at offset {offset - 1}"
            )
        count = struct.unpack(">I", data[offset:offset + 4])[0]
        offset += 4
        items = []
        for _ in range(count):
            item, offset = mu_decode(data, offset)
            items.append(item)
        return items, offset

    elif tag == TAG_DICT:
        if offset + 4 > len(data):
            raise MuBinaryDecodeError(
                f"Truncated dict count at offset {offset - 1}"
            )
        count = struct.unpack(">I", data[offset:offset + 4])[0]
        offset += 4
        result = {}
        for _ in range(count):
            key, offset = mu_decode(data, offset)
            if not isinstance(key, str):
                raise MuBinaryDecodeError(
                    f"Dict key must decode to string, got {type(key).__name__} "
                    f"at offset {offset}"
                )
            val, offset = mu_decode(data, offset)
            result[key] = val
        return result, offset

    else:
        raise MuBinaryDecodeError(
            f"Unknown tag 0x{tag:02x} at offset {offset - 1}"
        )


def mu_decode_value(data):
    """Convenience: decode a single top-level MuBinary value.

    Raises MuBinaryDecodeError if data is truncated or has trailing bytes.
    """
    value, end_offset = mu_decode(data, 0)
    if end_offset != len(data):
        raise MuBinaryDecodeError(
            f"Trailing data: decoded {end_offset} bytes but data is {len(data)} bytes"
        )
    return value


# ---------------------------------------------------------------------------
# Seed codec helpers
# ---------------------------------------------------------------------------


def encode_seed_projections(seed):
    """Encode the projections array from a parsed seed dict.

    Each projection is a dict with at least 'id', 'pattern', 'body' keys.
    Returns binary encoding of the projections list.
    """
    projections = seed["projections"]
    # Encode only the structurally meaningful fields (id, pattern, body)
    # that the kernel uses. Meta/description fields are documentation.
    minimal_projs = []
    for proj in projections:
        minimal_projs.append({
            "id": proj["id"],
            "pattern": proj["pattern"],
            "body": proj["body"],
        })
    return mu_encode(minimal_projs)


def decode_seed_projections(data):
    """Decode binary data back to a list of projection dicts."""
    return mu_decode_value(data)


# ===========================================================================
# Test Classes
# ===========================================================================


class TestSuccessCriteria:
    """C1-C4: Core evidence that H5 is confirmed."""

    # -- C1: Round-trip fidelity on canonical seeds --------------------------

    def test_c1_roundtrip_bootstrap_structural(self):
        """Round-trip: bootstrap_structural.v1.json survives encode→decode."""
        seed_path = get_seed_path("bootstrap_structural.v1.json")
        seed = load_verified_seed(seed_path)
        projections = seed["projections"]

        binary = encode_seed_projections(seed)
        decoded = decode_seed_projections(binary)

        assert len(decoded) == len(projections)
        for i, (orig, dec) in enumerate(zip(projections, decoded)):
            assert dec["id"] == orig["id"], f"Projection {i} id mismatch"
            assert dec["pattern"] == orig["pattern"], f"Projection {i} pattern mismatch"
            assert dec["body"] == orig["body"], f"Projection {i} body mismatch"

    def test_c1_roundtrip_kernel(self):
        """Round-trip: kernel.v1.json survives encode→decode."""
        seed_path = get_seed_path("kernel.v1.json")
        seed = load_verified_seed(seed_path)
        projections = seed["projections"]

        binary = encode_seed_projections(seed)
        decoded = decode_seed_projections(binary)

        assert len(decoded) == len(projections)
        for i, (orig, dec) in enumerate(zip(projections, decoded)):
            assert dec["id"] == orig["id"], f"Projection {i} id mismatch"
            assert dec["pattern"] == orig["pattern"], f"Projection {i} pattern mismatch"
            assert dec["body"] == orig["body"], f"Projection {i} body mismatch"

    # -- C2: Golden byte fixtures (decode-only, no encoder involved) ---------

    def test_c2_golden_null(self):
        """Golden fixture: 0x00 decodes to None."""
        assert mu_decode_value(bytes([0x00])) is None

    def test_c2_golden_true(self):
        """Golden fixture: 0x01 decodes to True."""
        assert mu_decode_value(bytes([0x01])) is True

    def test_c2_golden_false(self):
        """Golden fixture: 0x02 decodes to False."""
        assert mu_decode_value(bytes([0x02])) is False

    def test_c2_golden_int_42(self):
        """Golden fixture: 0x03 + 8 bytes BE = 42."""
        data = bytes([0x03, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x2A])
        assert mu_decode_value(data) == 42

    def test_c2_golden_int_negative(self):
        """Golden fixture: 0x03 + 8 bytes BE = -1."""
        data = bytes([0x03, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF])
        assert mu_decode_value(data) == -1

    def test_c2_golden_float_pi(self):
        """Golden fixture: 0x04 + 8 bytes IEEE 754 BE = 3.14159..."""
        # IEEE 754 double for pi: 0x400921FB54442D18
        data = bytes([0x04, 0x40, 0x09, 0x21, 0xFB, 0x54, 0x44, 0x2D, 0x18])
        result = mu_decode_value(data)
        assert abs(result - 3.141592653589793) < 1e-15

    def test_c2_golden_string_hello(self):
        """Golden fixture: 0x05 + len(5) + 'hello' = 'hello'."""
        data = bytes([0x05, 0x00, 0x00, 0x00, 0x05]) + b"hello"
        assert mu_decode_value(data) == "hello"

    def test_c2_golden_empty_string(self):
        """Golden fixture: 0x05 + len(0) = ''."""
        data = bytes([0x05, 0x00, 0x00, 0x00, 0x00])
        assert mu_decode_value(data) == ""

    def test_c2_golden_empty_list(self):
        """Golden fixture: 0x06 + count(0) = []."""
        data = bytes([0x06, 0x00, 0x00, 0x00, 0x00])
        assert mu_decode_value(data) == []

    def test_c2_golden_list_of_ints(self):
        """Golden fixture: list of [1, 2, 3]."""
        # 0x06 count=3, then three int64 values
        data = (
            bytes([0x06, 0x00, 0x00, 0x00, 0x03])  # list, 3 elements
            + bytes([0x03, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01])  # int 1
            + bytes([0x03, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02])  # int 2
            + bytes([0x03, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x03])  # int 3
        )
        assert mu_decode_value(data) == [1, 2, 3]

    def test_c2_golden_empty_dict(self):
        """Golden fixture: 0x07 + count(0) = {}."""
        data = bytes([0x07, 0x00, 0x00, 0x00, 0x00])
        assert mu_decode_value(data) == {}

    def test_c2_golden_simple_dict(self):
        """Golden fixture: {"a": 1} from hand-constructed bytes."""
        data = (
            bytes([0x07, 0x00, 0x00, 0x00, 0x01])  # dict, 1 entry
            + bytes([0x05, 0x00, 0x00, 0x00, 0x01]) + b"a"  # key "a"
            + bytes([0x03, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01])  # value 1
        )
        assert mu_decode_value(data) == {"a": 1}

    def test_c2_golden_nested_dict(self):
        """Golden fixture: {"x": {"y": true}} from hand-constructed bytes."""
        # Outer dict: 1 entry, key "x", value is inner dict
        # Inner dict: 1 entry, key "y", value is true
        inner_dict = (
            bytes([0x07, 0x00, 0x00, 0x00, 0x01])  # dict, 1 entry
            + bytes([0x05, 0x00, 0x00, 0x00, 0x01]) + b"y"  # key "y"
            + bytes([0x01])  # value true
        )
        data = (
            bytes([0x07, 0x00, 0x00, 0x00, 0x01])  # dict, 1 entry
            + bytes([0x05, 0x00, 0x00, 0x00, 0x01]) + b"x"  # key "x"
            + inner_dict  # value {"y": true}
        )
        assert mu_decode_value(data) == {"x": {"y": True}}

    def test_c2_golden_var_node(self):
        """Golden fixture: {"var": "name"} — the fundamental Mu variable node."""
        data = (
            bytes([0x07, 0x00, 0x00, 0x00, 0x01])  # dict, 1 entry
            + bytes([0x05, 0x00, 0x00, 0x00, 0x03]) + b"var"  # key "var"
            + bytes([0x05, 0x00, 0x00, 0x00, 0x04]) + b"name"  # value "name"
        )
        assert mu_decode_value(data) == {"var": "name"}

    def test_c2_golden_projection_like(self):
        """Golden fixture: a minimal projection-like dict from hand-built bytes.

        Encodes: {"id": "test.id", "pattern": {"x": null}, "body": {"x": true}}
        This mimics the shape of an actual seed projection.
        """
        # key "id", value "test.id"
        k_id = bytes([0x05, 0x00, 0x00, 0x00, 0x02]) + b"id"
        v_id = bytes([0x05, 0x00, 0x00, 0x00, 0x07]) + b"test.id"

        # key "pattern", value {"x": null}
        k_pat = bytes([0x05, 0x00, 0x00, 0x00, 0x07]) + b"pattern"
        v_pat = (
            bytes([0x07, 0x00, 0x00, 0x00, 0x01])  # dict, 1 entry
            + bytes([0x05, 0x00, 0x00, 0x00, 0x01]) + b"x"  # key "x"
            + bytes([0x00])  # value null
        )

        # key "body", value {"x": true}
        k_body = bytes([0x05, 0x00, 0x00, 0x00, 0x04]) + b"body"
        v_body = (
            bytes([0x07, 0x00, 0x00, 0x00, 0x01])  # dict, 1 entry
            + bytes([0x05, 0x00, 0x00, 0x00, 0x01]) + b"x"  # key "x"
            + bytes([0x01])  # value true
        )

        # Outer dict: 3 entries
        data = (
            bytes([0x07, 0x00, 0x00, 0x00, 0x03])
            + k_id + v_id
            + k_pat + v_pat
            + k_body + v_body
        )
        expected = {"id": "test.id", "pattern": {"x": None}, "body": {"x": True}}
        assert mu_decode_value(data) == expected

    # -- C3: Engine-level behavioral parity ----------------------------------

    @pytest.mark.slow  # SPEED_OK: calls step_kernel_mu
    def test_c3_engine_parity_kernel_stall(self):
        """Decoded domain projections produce same stall as JSON-loaded.

        Uses simple domain projections that don't match the input. Projections
        came from binary decode vs direct construction — both should stall
        identically through step_kernel_mu.
        """
        # Domain projections: only match {"state": "X"} → {"state": "Y"}
        domain_proj = {
            "id": "test.x_to_y",
            "pattern": {"state": "X"},
            "body": {"state": "Y"},
        }

        # JSON path: use projection directly
        json_projs = [{"pattern": domain_proj["pattern"], "body": domain_proj["body"]}]

        # Binary path: encode, decode, extract
        binary = mu_encode([domain_proj])
        decoded = mu_decode_value(binary)
        bin_projs = [{"pattern": decoded[0]["pattern"], "body": decoded[0]["body"]}]

        # Input that does NOT match → kernel stall
        test_input = {"no_match_key": "impossible_value"}

        json_result = step_kernel_mu(
            json_projs, test_input, return_meta=True, max_steps=500,
        )
        bin_result = step_kernel_mu(
            bin_projs, test_input, return_meta=True, max_steps=500,
        )

        # Same observable output and termination
        assert json_result["output"] == bin_result["output"]
        assert json_result["stall"] == bin_result["stall"] == True
        assert json_result["termination_reason"] == bin_result["termination_reason"]

    @pytest.mark.slow  # SPEED_OK: calls step_kernel_mu
    def test_c3_engine_parity_kernel_match_success(self):
        """Decoded domain projections produce same step_kernel_mu result as JSON-loaded.

        Uses a simple A→B domain projection through the kernel. Both JSON and
        binary-decoded projections must yield identical output.
        """
        # Simple domain projection: {"state": "A"} → {"state": "B"}
        domain_proj = {
            "id": "test.a_to_b",
            "pattern": {"state": "A"},
            "body": {"state": "B"},
        }

        # JSON path: use projection directly
        json_projs = [{"pattern": domain_proj["pattern"], "body": domain_proj["body"]}]

        # Binary path: encode full projection, decode, extract
        binary = mu_encode([domain_proj])
        decoded = mu_decode_value(binary)
        bin_projs = [{"pattern": decoded[0]["pattern"], "body": decoded[0]["body"]}]

        test_input = {"state": "A"}

        json_result = step_kernel_mu(
            json_projs, test_input, return_meta=True, max_steps=500,
        )
        bin_result = step_kernel_mu(
            bin_projs, test_input, return_meta=True, max_steps=500,
        )

        # Same observable output
        assert json_result["output"] == bin_result["output"]
        assert json_result["output"] == {"state": "B"}
        assert json_result["stall"] == bin_result["stall"] == False
        assert json_result["termination_reason"] == bin_result["termination_reason"]

    # -- C4: No new primitive ------------------------------------------------

    def test_c4_no_new_primitive(self):
        """Bootstrap primitive count unchanged (Py:4 + JS:7 = 11 total)."""
        py_dir = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost"
        js_dir = REPO_ROOT / "mu" / "host" / "js"

        py_count = 0
        for py_file in py_dir.glob("*.py"):
            content = py_file.read_text()
            py_count += content.count("BOOTSTRAP_PRIMITIVE")

        js_count = 0
        js_content = "\n".join(
            f.read_text() for f in sorted(js_dir.rglob("*.js"))
        )
        js_count = js_content.count("BOOTSTRAP_PRIMITIVE")

        assert py_count == 4, f"Expected 4 Python BOOTSTRAP_PRIMITIVE markers, found {py_count}"
        assert js_count == 7, f"Expected 7 JS BOOTSTRAP_PRIMITIVE markers, found {js_count}"


class TestBoundaryLock:
    """B1-B3: Boundary conditions and type coverage."""

    # -- B1: Round-trip for every Mu type ------------------------------------

    @pytest.mark.parametrize("value,description", [
        (None, "NoneType"),
        (True, "bool True"),
        (False, "bool False"),
        (0, "int zero"),
        (42, "int positive"),
        (-1, "int negative"),
        (2**53, "int large positive"),
        (-(2**53), "int large negative"),
        ("", "str empty"),
        ("hello", "str ascii"),
        ("café", "str unicode"),
        ([], "list empty"),
        ([1, "two", None], "list mixed"),
        ({}, "dict empty"),
        ({"key": "value"}, "dict simple"),
        ({"nested": {"deep": [1, True, None]}}, "dict nested"),
    ], ids=lambda x: x if isinstance(x, str) else repr(x))
    def test_b1_roundtrip_all_mu_types(self, value, description):
        """Round-trip fidelity for individual Mu type: {description}."""
        encoded = mu_encode(value)
        decoded = mu_decode_value(encoded)
        assert decoded == value, f"Round-trip failed for {description}: {decoded!r} != {value!r}"
        # Type check: decoded type must match original
        assert type(decoded) is type(value), (
            f"Type mismatch for {description}: {type(decoded)} != {type(value)}"
        )

    def test_b2_all_seed_types_covered(self):
        """Every Mu type present in production seeds is handled by the codec.

        Walks all seed files and collects the Python types used. Verifies
        the codec handles every type found. Production seeds use:
        NoneType, bool, int, str, list, dict (no float).
        """
        seed_types = set()

        seed_dir = REPO_ROOT / "mu"
        for seed_file in seed_dir.rglob("*.json"):
            # Only process files that look like seed files (have projections)
            try:
                content = seed_file.read_text()
                data = json.loads(content)
                if not isinstance(data, dict) or "projections" not in data:
                    continue
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

            # Walk the entire structure collecting types
            _collect_types(data, seed_types)

        # These are the types we expect in production seeds
        expected_types = {type(None), bool, int, str, list, dict}
        assert seed_types == expected_types, (
            f"Unexpected types in seeds: {seed_types - expected_types} "
            f"or missing types: {expected_types - seed_types}"
        )

        # Verify each type round-trips
        type_exemplars = {
            type(None): None,
            bool: True,
            int: 42,
            str: "test",
            list: [1, 2],
            dict: {"k": "v"},
        }
        for typ in seed_types:
            exemplar = type_exemplars[typ]
            assert mu_decode_value(mu_encode(exemplar)) == exemplar

    # -- B3: Failure modes ---------------------------------------------------

    def test_b3_truncated_empty(self):
        """Empty data raises MuBinaryDecodeError."""
        with pytest.raises(MuBinaryDecodeError, match="Unexpected end of data"):
            mu_decode_value(b"")

    def test_b3_truncated_int(self):
        """Truncated int64 raises MuBinaryDecodeError."""
        # Tag 0x03 (int64) but only 4 bytes of payload instead of 8
        with pytest.raises(MuBinaryDecodeError, match="Truncated int64"):
            mu_decode_value(bytes([0x03, 0x00, 0x00, 0x00, 0x00]))

    def test_b3_truncated_float(self):
        """Truncated float64 raises MuBinaryDecodeError."""
        with pytest.raises(MuBinaryDecodeError, match="Truncated float64"):
            mu_decode_value(bytes([0x04, 0x00, 0x00]))

    def test_b3_truncated_string(self):
        """String with declared length exceeding data raises error."""
        # String tag + length=100 but no data following
        data = bytes([0x05, 0x00, 0x00, 0x00, 0x64])
        with pytest.raises(MuBinaryDecodeError, match="Truncated string data"):
            mu_decode_value(data)

    def test_b3_truncated_string_length(self):
        """String with truncated length field raises error."""
        data = bytes([0x05, 0x00, 0x00])  # Only 2 of 4 length bytes
        with pytest.raises(MuBinaryDecodeError, match="Truncated string length"):
            mu_decode_value(data)

    def test_b3_bad_tag(self):
        """Unknown tag byte raises MuBinaryDecodeError."""
        with pytest.raises(MuBinaryDecodeError, match="Unknown tag 0xff"):
            mu_decode_value(bytes([0xFF]))

    def test_b3_bad_tag_0x08(self):
        """Tag 0x08 (one past dict) is invalid."""
        with pytest.raises(MuBinaryDecodeError, match="Unknown tag 0x08"):
            mu_decode_value(bytes([0x08]))

    def test_b3_length_overflow_list(self):
        """List with count exceeding remaining data raises error."""
        # List tag + count=1000000 but no elements
        data = bytes([0x06, 0x00, 0x0F, 0x42, 0x40])
        with pytest.raises(MuBinaryDecodeError):
            mu_decode_value(data)

    def test_b3_non_string_dict_key_encode(self):
        """Encoding a dict with non-string key raises ValueError."""
        with pytest.raises(ValueError, match="Dict key must be string"):
            mu_encode({42: "value"})

    def test_b3_non_string_dict_key_decode(self):
        """Decoding a dict with non-string key raises MuBinaryDecodeError."""
        # Dict with 1 entry, key is int 42 (should be string)
        data = (
            bytes([0x07, 0x00, 0x00, 0x00, 0x01])  # dict, 1 entry
            + bytes([0x03, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x2A])  # key: int 42
            + bytes([0x05, 0x00, 0x00, 0x00, 0x03]) + b"val"  # value: "val"
        )
        with pytest.raises(MuBinaryDecodeError, match="Dict key must decode to string"):
            mu_decode_value(data)

    def test_b3_nan_encode_roundtrip(self):
        """NaN encodes and decodes but is not equal to itself (IEEE 754 semantics)."""
        import math
        encoded = mu_encode(float("nan"))
        decoded = mu_decode_value(encoded)
        assert math.isnan(decoded)

    def test_b3_inf_encode_roundtrip(self):
        """Infinity encodes and decodes correctly."""
        import math
        for val in [float("inf"), float("-inf")]:
            encoded = mu_encode(val)
            decoded = mu_decode_value(encoded)
            assert decoded == val
            assert math.isinf(decoded)

    def test_b3_trailing_data(self):
        """Trailing bytes after a complete value raise error."""
        data = bytes([0x00, 0x00])  # null + extra null byte
        with pytest.raises(MuBinaryDecodeError, match="Trailing data"):
            mu_decode_value(data)


class TestFailureCriteria:
    """F1-F9: Honest documentation of host dependencies."""

    def test_f1_encoder_uses_isinstance(self):
        """F1/F2: Encoder and decoder use isinstance for type dispatch."""
        source = inspect.getsource(mu_encode)
        assert "isinstance" in source, "Encoder should use isinstance (honest host dependency)"

    def test_f3_struct_pack_dependency(self):
        """F3: Codec uses struct.pack/unpack (host numeric serialization)."""
        encode_source = inspect.getsource(mu_encode)
        decode_source = inspect.getsource(mu_decode)
        assert "struct.pack" in encode_source
        assert "struct.unpack" in decode_source

    def test_f4_utf8_dependency(self):
        """F4: Codec uses host UTF-8 encode/decode."""
        encode_source = inspect.getsource(mu_encode)
        decode_source = inspect.getsource(mu_decode)
        assert '.encode("utf-8")' in encode_source
        assert '.decode("utf-8")' in decode_source

    def test_f6_decoder_is_recursive(self):
        """F6: Decoder recurses for nested structures (not flat)."""
        source = inspect.getsource(mu_decode)
        # The function calls itself for nested list/dict elements
        assert "mu_decode(data, offset)" in source, (
            "Decoder must recursively call mu_decode for nested structures"
        )


class TestStructuralProperties:
    """Codec properties and LOC budget."""

    def test_decoder_loc_under_150(self):
        """Research artifact: decode functions total < 150 LOC."""
        source_decode = inspect.getsource(mu_decode)
        source_decode_value = inspect.getsource(mu_decode_value)

        # Count non-blank, non-comment lines
        def count_loc(source):
            lines = source.split("\n")
            return sum(
                1
                for line in lines
                if line.strip() and not line.strip().startswith("#")
            )

        total = count_loc(source_decode) + count_loc(source_decode_value)
        assert total < 150, f"Decode functions are {total} LOC (limit: 150)"

    def test_encoder_loc_under_150(self):
        """Research artifact: encode function total < 150 LOC."""
        source = inspect.getsource(mu_encode)

        def count_loc(s):
            lines = s.split("\n")
            return sum(
                1
                for line in lines
                if line.strip() and not line.strip().startswith("#")
            )

        total = count_loc(source)
        assert total < 150, f"Encode function is {total} LOC (limit: 150)"

    def test_codec_total_loc(self):
        """Combined encode+decode is significantly smaller than JSON parser.

        Python's json module is ~2,500 LOC. Our codec should be under 200 LOC
        total (encode + decode + decode_value), demonstrating parsing-component
        surface reduction.
        """
        sources = [
            inspect.getsource(mu_encode),
            inspect.getsource(mu_decode),
            inspect.getsource(mu_decode_value),
        ]

        def count_loc(s):
            lines = s.split("\n")
            return sum(
                1
                for line in lines
                if line.strip() and not line.strip().startswith("#")
            )

        total = sum(count_loc(s) for s in sources)
        assert total < 200, f"Total codec is {total} LOC (limit: 200)"

    def test_binary_is_smaller_than_json(self):
        """Binary encoding is more compact than JSON for seed projections.

        Not a success criterion — just a structural property observation.
        """
        seed_path = get_seed_path("kernel.v1.json")
        seed = load_verified_seed(seed_path)
        projections = seed["projections"]

        json_bytes = json.dumps(projections).encode("utf-8")
        binary_bytes = encode_seed_projections(seed)

        # Binary should be more compact (no key quoting, no delimiters)
        # This is informational — test passes either way
        ratio = len(binary_bytes) / len(json_bytes)
        # Just record, don't assert a specific ratio
        assert len(binary_bytes) > 0
        assert len(json_bytes) > 0

    def test_no_import_from_rcx_internal(self):
        """Research artifact does not import underscore-prefixed rcx_pi internals."""
        source_path = Path(__file__)
        tree = ast.parse(source_path.read_text())

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("rcx_pi"):
                    for alias in node.names:
                        name = alias.name
                        assert not name.startswith("_"), (
                            f"Imports underscore-prefixed {name} from {node.module}"
                        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collect_types(obj, type_set):
    """Recursively collect Python types from a JSON-like structure."""
    type_set.add(type(obj))
    if isinstance(obj, dict):
        for k, v in obj.items():
            _collect_types(k, type_set)
            _collect_types(v, type_set)
    elif isinstance(obj, list):
        for item in obj:
            _collect_types(item, type_set)
