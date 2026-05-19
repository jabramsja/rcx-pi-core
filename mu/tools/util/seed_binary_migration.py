#!/usr/bin/env python3
"""Generate and validate deterministic seed binary sidecar artifacts.

This tool does not change production seed loading. It reads an already-valid
JSON seed image, writes a smaller MuBinary projection sidecar, and emits a
checksum proof chain that can be validated without flipping the JSON rollback
path.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


def _find_repo_root() -> Path:
    cursor = Path(__file__).resolve()
    for parent in (cursor.parent, *cursor.parents):
        if (parent / "pyproject.toml").is_file():
            return parent
    raise RuntimeError("Cannot find repo root from seed_binary_migration.py")


REPO_ROOT = _find_repo_root()
PY_HOST = REPO_ROOT / "mu" / "host" / "python"
if str(PY_HOST) not in sys.path:
    sys.path.insert(0, str(PY_HOST))

from rcx_pi.selfhost.seed_integrity import (  # noqa: E402
    EXPECTED_PROJECTION_IDS,
    SEED_REGISTRY_MANIFEST,
    SEED_BINARY_CHECKSUM_POLICY_ID,
    SEED_BINARY_MIGRATION_POLICY_ID,
    SeedBinaryMigrationError,
    compute_checksum,
    load_verified_seed_image,
)

_JS_SAFE_INTEGER_LIMIT = 2**53
_TAG_NULL = 0x00
_TAG_TRUE = 0x01
_TAG_FALSE = 0x02
_TAG_INT64 = 0x03
_TAG_FLOAT64 = 0x04
_TAG_STRING = 0x05
_TAG_LIST = 0x06
_TAG_DICT = 0x07
_PROJECTION_KEY_ORDER = ("id", "pattern", "body")


def _require_policy(policy_id: str) -> None:
    if policy_id != SEED_BINARY_MIGRATION_POLICY_ID:
        raise SeedBinaryMigrationError(
            f"Unsupported seed binary migration policy: {policy_id!r}"
        )


def _require_js_cli_registered_seed(seed_name: str) -> None:
    manifest_seeds = SEED_REGISTRY_MANIFEST.get("seeds")
    record = manifest_seeds.get(seed_name) if isinstance(manifest_seeds, dict) else None
    if not isinstance(record, dict) or record.get("js_cli_registered") is not True:
        raise SeedBinaryMigrationError(
            f"Seed binary migration requires JS CLI verification registry coverage: "
            f"{seed_name} is not registered in SEED_CHECKSUMS"
        )


def _require_available(
    data: bytes,
    offset: int,
    length: int,
    label: str,
    tag_offset: int,
) -> None:
    if offset + length <= len(data):
        return
    have = max(len(data) - offset, 0)
    raise SeedBinaryMigrationError(
        f"Truncated {label} at offset {tag_offset} "
        f"(need {length} bytes, have {have})"
    )


def _encode_value(value: Any, path_label: str) -> bytes:
    if value is None:
        return bytes([_TAG_NULL])
    if isinstance(value, bool):
        return bytes([_TAG_TRUE if value else _TAG_FALSE])
    if isinstance(value, int):
        if not (-_JS_SAFE_INTEGER_LIMIT <= value <= _JS_SAFE_INTEGER_LIMIT):
            raise SeedBinaryMigrationError(
                f"Integer at {path_label} is outside exact JS integer binary policy: "
                f"{value}"
            )
        return bytes([_TAG_INT64]) + value.to_bytes(8, "big", signed=True)
    if isinstance(value, float):
        raise SeedBinaryMigrationError(
            f"Float at {path_label} is unsupported by seed binary migration policy"
        )
    if isinstance(value, str):
        encoded = value.encode("utf-8")
        return bytes([_TAG_STRING]) + len(encoded).to_bytes(4, "big") + encoded
    if isinstance(value, list):
        parts = [bytes([_TAG_LIST]) + len(value).to_bytes(4, "big")]
        for index, item in enumerate(value):
            parts.append(_encode_value(item, f"{path_label}[{index}]"))
        return b"".join(parts)
    if isinstance(value, dict):
        for key in value:
            if not isinstance(key, str):
                raise SeedBinaryMigrationError(
                    f"Dict key at {path_label} must be string, got {type(key).__name__}"
                )
        parts = [bytes([_TAG_DICT]) + len(value).to_bytes(4, "big")]
        for key, nested in value.items():
            parts.append(_encode_value(key, f"{path_label}.<key>"))
            parts.append(_encode_value(nested, f"{path_label}.{key}"))
        return b"".join(parts)
    raise SeedBinaryMigrationError(
        f"Unsupported value at {path_label}: {type(value).__name__}"
    )


def _decode_at(data: bytes, offset: int) -> tuple[Any, int]:
    if offset >= len(data):
        raise SeedBinaryMigrationError(
            f"Unexpected end of data at offset {offset} (data length {len(data)})"
        )

    tag_offset = offset
    tag = data[offset]
    offset += 1

    if tag == _TAG_NULL:
        return None, offset
    if tag == _TAG_TRUE:
        return True, offset
    if tag == _TAG_FALSE:
        return False, offset
    if tag == _TAG_INT64:
        _require_available(data, offset, 8, "int64", tag_offset)
        value = int.from_bytes(data[offset: offset + 8], "big", signed=True)
        if not (-_JS_SAFE_INTEGER_LIMIT <= value <= _JS_SAFE_INTEGER_LIMIT):
            raise SeedBinaryMigrationError(
                f"int64 at offset {tag_offset} cannot be represented exactly "
                "as a JavaScript Number"
            )
        return value, offset + 8
    if tag == _TAG_FLOAT64:
        _require_available(data, offset, 8, "float64", tag_offset)
        raise SeedBinaryMigrationError(
            "Seed binary projection contains FLOAT64 numeric data; "
            "current seed images are integer-only"
        )
    if tag == _TAG_STRING:
        _require_available(data, offset, 4, "string length", tag_offset)
        length = int.from_bytes(data[offset: offset + 4], "big")
        offset += 4
        _require_available(data, offset, length, "string data", tag_offset)
        try:
            return data[offset: offset + length].decode("utf-8"), offset + length
        except UnicodeDecodeError as exc:
            raise SeedBinaryMigrationError(
                f"Malformed UTF-8 string at offset {tag_offset}: {exc}"
            ) from exc
    if tag == _TAG_LIST:
        _require_available(data, offset, 4, "list count", tag_offset)
        count = int.from_bytes(data[offset: offset + 4], "big")
        offset += 4
        items = []
        for _ in range(count):
            item, offset = _decode_at(data, offset)
            items.append(item)
        return items, offset
    if tag == _TAG_DICT:
        _require_available(data, offset, 4, "dict count", tag_offset)
        count = int.from_bytes(data[offset: offset + 4], "big")
        offset += 4
        result: dict[str, Any] = {}
        for _ in range(count):
            key, offset = _decode_at(data, offset)
            if not isinstance(key, str):
                raise SeedBinaryMigrationError(
                    f"Dict key must decode to string, got {type(key).__name__} "
                    f"at offset {offset}"
                )
            if key in result:
                raise SeedBinaryMigrationError(
                    f"Duplicate dict key {key!r} at offset {tag_offset}"
                )
            nested, offset = _decode_at(data, offset)
            result[key] = nested
        return result, offset
    raise SeedBinaryMigrationError(f"Unknown tag 0x{tag:02x} at offset {tag_offset}")


def _ordered_equal(left: Any, right: Any) -> bool:
    if isinstance(left, dict) and isinstance(right, dict):
        if list(left.keys()) != list(right.keys()):
            return False
        return all(_ordered_equal(left[key], right[key]) for key in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            _ordered_equal(left_item, right_item)
            for left_item, right_item in zip(left, right)
        )
    return left == right


def _proof_value_equal(expected: Any, computed: Any) -> bool:
    if isinstance(expected, bool) or isinstance(computed, bool):
        return (
            isinstance(expected, bool)
            and isinstance(computed, bool)
            and expected == computed
        )
    if isinstance(expected, dict) and isinstance(computed, dict):
        if list(expected.keys()) != list(computed.keys()):
            return False
        return all(
            _proof_value_equal(expected[key], computed[key])
            for key in expected
        )
    if isinstance(expected, list) and isinstance(computed, list):
        return len(expected) == len(computed) and all(
            _proof_value_equal(expected_item, computed_item)
            for expected_item, computed_item in zip(expected, computed)
        )
    if type(expected) is not type(computed):
        return False
    return expected == computed


def _minimal_projections(seed: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": projection["id"],
            "pattern": projection["pattern"],
            "body": projection["body"],
        }
        for projection in seed["projections"]
    ]


def encode_seed_binary_projections(
    projections: list[dict[str, Any]],
    *,
    policy_id: str = SEED_BINARY_MIGRATION_POLICY_ID,
) -> bytes:
    _require_policy(policy_id)
    return _encode_value(projections, "projections")


def decode_seed_binary_projections(binary_image: bytes) -> list[dict[str, Any]]:
    decoded, end_offset = _decode_at(bytes(binary_image), 0)
    if end_offset != len(binary_image):
        raise SeedBinaryMigrationError(
            f"Trailing data: decoded {end_offset} bytes but data is {len(binary_image)} bytes"
        )
    if not isinstance(decoded, list):
        raise SeedBinaryMigrationError(
            "Seed binary image must decode to projections array, got "
            f"{type(decoded).__name__}"
        )
    for index, projection in enumerate(decoded):
        if not isinstance(projection, dict):
            raise SeedBinaryMigrationError(
                f"Seed binary projection[{index}] must be a dict, "
                f"got {type(projection).__name__}"
            )
        for key in ("id", "pattern", "body"):
            if key not in projection:
                raise SeedBinaryMigrationError(
                    f"Seed binary projection {index} missing key {key!r}"
                )
        if list(projection.keys()) != list(_PROJECTION_KEY_ORDER):
            raise SeedBinaryMigrationError(
                f"Seed binary projection {index} has non-canonical key order: "
                f"{list(projection.keys())}"
            )
        if not isinstance(projection["id"], str):
            raise SeedBinaryMigrationError(
                f"Seed binary projection {index} id must be a string, "
                f"got {type(projection['id']).__name__}"
            )
    return decoded


def _proof_chain_payload(
    *,
    seed_name: str,
    json_sha256: str,
    binary_sha256: str,
    projection_ids: list[str],
    policy_id: str,
) -> dict[str, Any]:
    return {
        "binary_sha256": binary_sha256,
        "checksum_policy_id": SEED_BINARY_CHECKSUM_POLICY_ID,
        "json_sha256": json_sha256,
        "migration_policy_id": policy_id,
        "projection_ids": projection_ids,
        "seed_name": seed_name,
    }


def _proof_chain_sha256(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return compute_checksum(canonical)


def build_seed_binary_migration_proof(
    seed_name: str,
    seed_bytes: bytes,
    binary_image: bytes,
    *,
    policy_id: str = SEED_BINARY_MIGRATION_POLICY_ID,
) -> dict[str, Any]:
    _require_policy(policy_id)
    _require_js_cli_registered_seed(seed_name)
    seed = load_verified_seed_image(seed_name, seed_bytes, verify=True)
    expected_projections = _minimal_projections(seed)
    decoded_projections = decode_seed_binary_projections(binary_image)

    expected_ids = EXPECTED_PROJECTION_IDS[seed_name]
    decoded_ids = [projection["id"] for projection in decoded_projections]
    if decoded_ids != expected_ids:
        raise SeedBinaryMigrationError(
            f"Seed binary projection ID mismatch for {seed_name}: "
            f"expected {expected_ids}, got {decoded_ids}"
        )
    if not _ordered_equal(decoded_projections, expected_projections):
        raise SeedBinaryMigrationError(
            f"Seed binary source/binary mismatch for {seed_name}"
        )
    if len(binary_image) >= len(seed_bytes):
        raise SeedBinaryMigrationError(
            f"Generated seed binary image for {seed_name} is not smaller than JSON "
            f"({len(binary_image)} >= {len(seed_bytes)})"
        )

    json_sha256 = compute_checksum(seed_bytes)
    binary_sha256 = compute_checksum(binary_image)
    chain_payload = _proof_chain_payload(
        seed_name=seed_name,
        json_sha256=json_sha256,
        binary_sha256=binary_sha256,
        projection_ids=decoded_ids,
        policy_id=policy_id,
    )
    return {
        "seed_name": seed_name,
        "migration_policy_id": policy_id,
        "checksum_policy_id": SEED_BINARY_CHECKSUM_POLICY_ID,
        "json_sha256": json_sha256,
        "binary_sha256": binary_sha256,
        "proof_chain_sha256": _proof_chain_sha256(chain_payload),
        "projection_ids": decoded_ids,
        "projection_count": len(decoded_projections),
        "json_size": len(seed_bytes),
        "binary_size": len(binary_image),
        "binary_is_smaller": len(binary_image) < len(seed_bytes),
    }


def generate_seed_binary_migration_artifact(
    seed_name: str,
    seed_bytes: bytes,
    *,
    policy_id: str = SEED_BINARY_MIGRATION_POLICY_ID,
) -> tuple[bytes, dict[str, Any]]:
    _require_policy(policy_id)
    _require_js_cli_registered_seed(seed_name)
    seed = load_verified_seed_image(seed_name, seed_bytes, verify=True)
    projections = _minimal_projections(seed)
    binary_image = encode_seed_binary_projections(projections, policy_id=policy_id)
    if len(binary_image) >= len(seed_bytes):
        raise SeedBinaryMigrationError(
            f"Generated seed binary image for {seed_name} is not smaller than JSON "
            f"({len(binary_image)} >= {len(seed_bytes)})"
        )
    proof = build_seed_binary_migration_proof(
        seed_name,
        seed_bytes,
        binary_image,
        policy_id=policy_id,
    )
    return binary_image, proof


def verify_seed_binary_migration_artifact(
    seed_name: str,
    seed_bytes: bytes,
    binary_image: bytes,
    expected_proof: dict[str, Any],
    *,
    policy_id: str = SEED_BINARY_MIGRATION_POLICY_ID,
) -> dict[str, Any]:
    if not isinstance(expected_proof, dict):
        raise SeedBinaryMigrationError("Seed binary proof must be a dict")

    computed_proof = build_seed_binary_migration_proof(
        seed_name,
        seed_bytes,
        binary_image,
        policy_id=policy_id,
    )
    if set(expected_proof) != set(computed_proof):
        raise SeedBinaryMigrationError(
            f"Seed binary proof key set mismatch for {seed_name}: "
            f"expected keys {sorted(expected_proof)}, got {sorted(computed_proof)}"
        )

    for key in sorted(computed_proof):
        if not _proof_value_equal(expected_proof.get(key), computed_proof[key]):
            raise SeedBinaryMigrationError(
                f"Seed binary proof mismatch for {seed_name}: {key} "
                f"expected {expected_proof.get(key)!r}, got {computed_proof[key]!r}"
            )
    return computed_proof


def _read_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise SystemExit(f"Failed to read {path}: {exc}") from exc


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Failed to read proof JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"Proof JSON must be an object: {path}")
    return payload


def _canonical_path(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _require_distinct_generate_paths(
    *,
    json_seed: Path,
    binary_out: Path,
    proof_out: Path,
) -> None:
    labeled_paths = {
        "json-seed": _canonical_path(json_seed),
        "binary-out": _canonical_path(binary_out),
        "proof-out": _canonical_path(proof_out),
    }
    seen: dict[Path, str] = {}
    for label, path in labeled_paths.items():
        previous = seen.get(path)
        if previous is not None:
            raise SeedBinaryMigrationError(
                "Seed binary migration generate paths must be distinct: "
                f"{previous} and {label} both resolve to {path}"
            )
        seen[path] = label


def _require_output_file_path(path: Path, label: str) -> None:
    if path.exists() and path.is_dir():
        raise SeedBinaryMigrationError(
            f"Seed binary migration {label} must be a file path, got directory: {path}"
        )


def _write_temp_bytes(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        raise
    return temp_path


def _backup_existing_output(path: Path) -> Path | None:
    if not path.exists() and not path.is_symlink():
        return None
    return _write_temp_bytes(path, path.read_bytes())


def _rollback_binary_output(path: Path, backup: Path | None) -> None:
    if backup is None:
        path.unlink(missing_ok=True)
        return
    backup.replace(path)


def _write_generate_outputs(
    *,
    binary_out: Path,
    binary_image: bytes,
    proof_out: Path,
    proof: dict[str, Any],
) -> None:
    _require_output_file_path(binary_out, "binary-out")
    _require_output_file_path(proof_out, "proof-out")
    proof_bytes = (
        json.dumps(proof, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    temp_binary: Path | None = None
    temp_proof: Path | None = None
    binary_backup: Path | None = None
    try:
        temp_binary = _write_temp_bytes(binary_out, binary_image)
        temp_proof = _write_temp_bytes(proof_out, proof_bytes)
        binary_backup = _backup_existing_output(binary_out)
        temp_binary.replace(binary_out)
        temp_binary = None
        try:
            temp_proof.replace(proof_out)
        except Exception as exc:
            try:
                _rollback_binary_output(binary_out, binary_backup)
                binary_backup = None
            except Exception as rollback_exc:
                raise SeedBinaryMigrationError(
                    "Seed binary migration failed after publishing binary "
                    f"output, and binary rollback failed: {rollback_exc}"
                ) from exc
            raise
        temp_proof = None
    finally:
        if temp_binary is not None:
            temp_binary.unlink(missing_ok=True)
        if temp_proof is not None:
            temp_proof.unlink(missing_ok=True)
        if binary_backup is not None:
            binary_backup.unlink(missing_ok=True)


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _cmd_generate(args: argparse.Namespace) -> int:
    _require_distinct_generate_paths(
        json_seed=args.json_seed,
        binary_out=args.binary_out,
        proof_out=args.proof_out,
    )
    seed_bytes = _read_bytes(args.json_seed)
    binary_image, proof = generate_seed_binary_migration_artifact(
        args.seed_name,
        seed_bytes,
    )
    _write_generate_outputs(
        binary_out=args.binary_out,
        binary_image=binary_image,
        proof_out=args.proof_out,
        proof=proof,
    )
    _print_json(proof)
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    seed_bytes = _read_bytes(args.json_seed)
    binary_image = _read_bytes(args.binary)
    expected_proof = _read_json(args.proof)
    proof = verify_seed_binary_migration_artifact(
        args.seed_name,
        seed_bytes,
        binary_image,
        expected_proof,
    )
    _print_json(proof)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate or validate seed binary migration sidecars.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser(
        "generate",
        help="Generate sidecar binary bytes and proof JSON from a seed JSON image.",
    )
    generate.add_argument("--seed-name", required=True)
    generate.add_argument("--json-seed", required=True, type=Path)
    generate.add_argument("--binary-out", required=True, type=Path)
    generate.add_argument("--proof-out", required=True, type=Path)
    generate.set_defaults(func=_cmd_generate)

    validate = subparsers.add_parser(
        "validate",
        help="Validate sidecar binary bytes against seed JSON and proof JSON.",
    )
    validate.add_argument("--seed-name", required=True)
    validate.add_argument("--json-seed", required=True, type=Path)
    validate.add_argument("--binary", required=True, type=Path)
    validate.add_argument("--proof", required=True, type=Path)
    validate.set_defaults(func=_cmd_validate)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:
        print(f"seed binary migration failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
