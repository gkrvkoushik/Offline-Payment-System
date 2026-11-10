"""Cryptographic hashing primitives with domain separation for audit trees."""

import hashlib
from typing import Union

LEAF_DOMAIN_PREFIX: bytes = b"\x00"
INTERNAL_DOMAIN_PREFIX: bytes = b"\x01"


def sha256_bytes(data: bytes) -> bytes:
    """Compute standard SHA-256 digest returning 32 bytes."""
    return hashlib.sha256(data).digest()


def sha256_hex(data: Union[bytes, str]) -> str:
    """Compute standard SHA-256 digest returning a 64-character hex string."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def domain_hash_leaf(data: bytes) -> bytes:
    """Compute domain-separated leaf hash: SHA-256(0x00 || data)."""
    return hashlib.sha256(LEAF_DOMAIN_PREFIX + data).digest()


def domain_hash_leaf_hex(data: bytes) -> str:
    """Compute domain-separated leaf hash returning a 64-character hex string."""
    return domain_hash_leaf(data).hex()


def domain_hash_node(left: bytes, right: bytes) -> bytes:
    """Compute domain-separated internal node hash: SHA-256(0x01 || left || right)."""
    if len(left) != 32 or len(right) != 32:
        raise ValueError(
            f"Internal node children must be exactly 32 bytes each. Got len(left)={len(left)}, len(right)={len(right)}"
        )
    return hashlib.sha256(INTERNAL_DOMAIN_PREFIX + left + right).digest()


def domain_hash_node_hex(left_hex: str, right_hex: str) -> str:
    """Compute domain-separated internal node hash from 64-character hex strings."""
    left = bytes.fromhex(left_hex.removeprefix("0x"))
    right = bytes.fromhex(right_hex.removeprefix("0x"))
    return domain_hash_node(left, right).hex()
