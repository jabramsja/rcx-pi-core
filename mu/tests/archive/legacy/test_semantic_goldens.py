import dataclasses
import json
import os
from pathlib import Path
from typing import Any

from rcx_omega.core import parse_motif
from rcx_omega.trace import PureEvaluator, trace_reduce

GOLDEN_DIR = Path(__file__).parent / "golden"


def _to_primitive(x: Any) -> Any:
    if x is None or isinstance(x, (bool, int, float, str)):
        return x
    if isinstance(x, (list, tuple)):
        return [_to_primitive(v) for v in x]
    if isinstance(x, dict):
        return {str(k): _to_primitive(v) for k, v in x.items()}
    if dataclasses.is_dataclass(x):
        return _to_primitive(dataclasses.asdict(x))
    if hasattr(x, "__dict__"):
        d = {}
        for k, v in vars(x).items():
            if k.startswith("_"):
                continue
            d[str(k)] = _to_primitive(v)
        return d
    return str(x)


def _normalize_trace_payload(obj: Any) -> dict:
    prim = _to_primitive(obj)
    if not isinstance(prim, dict):
        prim = {"trace": prim}

    # Freeze only what we *intend* to keep stable.
    # This avoids tests failing if you later add helpful metadata.
    keep_keys = [
        "schema_version",
        "schema",
        "version",
        "input",
        "expr",
        "result",
        "summary",
        "steps",
        "events",
        "trace",
    ]
    out = {k: prim[k] for k in keep_keys if k in prim}

    # If none of those keys exist (unexpected), keep everything so diffs are informative.
    return out if out else prim


def _semantic_trace(expr: str) -> dict:
    motif = parse_motif(expr)
    evaluator = PureEvaluator()
    tr = trace_reduce(evaluator, motif)  # current repo signature supports this ordering
    return _normalize_trace_payload(tr)


def _golden_path(name: str) -> Path:
    return GOLDEN_DIR / f"{name}.json"


def _write_json(path: Path, data: dict):
    path.write_text(
        json.dumps(data, sort_keys=True, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_matches_golden(name: str, data: dict):
    path = _golden_path(name)
    update = os.getenv("RCX_UPDATE_GOLDENS", "").strip() in {"1", "true", "yes", "on"}

    if update or not path.exists():
        _write_json(path, data)
        return

    expected = _read_json(path)
    assert data == expected, (
        f"Golden mismatch for {name}. To update intentionally: RCX_UPDATE_GOLDENS=1 pytest -q"
    )


def _semantic_trace_or_error(expr: str) -> dict:
    """
    Return a normalized semantic trace dict for valid expressions.
    For invalid expressions, return a normalized error contract dict.
    """
    try:
        return _semantic_trace(expr)
    except Exception as e:
        # Freeze failure contract without depending on exception repr noise
        return {
            "error": {
                "type": type(e).__name__,
                "message": str(e),
            },
            "expr": expr,
        }


def _semantic_trace_or_error(expr: str) -> dict:
    """
    Return a normalized semantic trace dict for valid expressions.
    For invalid expressions, return a normalized error contract dict.
    """
    try:
        return _semantic_trace(expr)
    except Exception as e:
        # Freeze failure contract without depending on exception repr noise
        return {
            "error": {
                "type": type(e).__name__,
                "message": str(e),
            },
            "expr": expr,
        }


def test_golden_semantic_trace_mu_mu():
    data = _semantic_trace_or_error("μ(μ())")
    _assert_matches_golden("semantic_trace__mu_mu", data)


def test_golden_semantic_trace_mu_empty():
    # Second "valid-ish" path. If this grammar is invalid in your system,
    # it will snapshot the error contract instead (still useful, but we'll adjust later).
    data = _semantic_trace_or_error("μ()")
    _assert_matches_golden("semantic_trace__mu_empty", data)


def test_golden_semantic_trace_invalid_expr_contract():
    # Deliberately invalid input to lock the error shape.
    data = _semantic_trace_or_error("μ(]")
    _assert_matches_golden("semantic_trace__invalid_expr", data)
