"""Deterministic canonical serialization for audit events (RFC 8785 compliant)."""

from enum import Enum
import json
from dataclasses import asdict, is_dataclass
from typing import Any


def _normalize_obj(obj: Any) -> Any:
    """Recursively normalize objects into JSON-serializable primitives with sorted keys."""
    if obj is None:
        return None
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, (int, str)):
        return obj
    if isinstance(obj, float):
        raise ValueError(
            f"Floating point numbers are forbidden in monetary audit canonicalization: {obj}"
        )
    if isinstance(obj, Enum):
        return obj.value
    if is_dataclass(obj) and not isinstance(obj, type):
        return _normalize_obj(asdict(obj))
    if isinstance(obj, dict):
        return {str(k): _normalize_obj(v) for k, v in sorted(obj.items())}
    if isinstance(obj, (list, tuple)):
        return [_normalize_obj(item) for item in obj]
    if isinstance(obj, bytes):
        return obj.hex()
    return str(obj)


def to_canonical_json(data: Any) -> str:
    """Serialize an object into a canonical, deterministic JSON string.

    Key properties:
    - Strictly sorted dictionary keys at all depths.
    - No whitespace between tokens (separators=(',', ':')).
    - UTF-8 representation without Unicode escapes.
    - Floating point numbers are explicitly forbidden to prevent IEEE 754 ambiguity.
    """
    normalized = _normalize_obj(data)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def canonicalize(data: Any) -> bytes:
    """Convert an object into deterministic canonical UTF-8 bytes for cryptographic hashing."""
    return to_canonical_json(data).encode("utf-8")
