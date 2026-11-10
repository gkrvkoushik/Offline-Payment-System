"""Canonical Merkle Tree generator with domain-separated hashing and inclusion proofs."""

import hashlib
from typing import List, Optional, Sequence, Union

from offline_payment.audit.events import AuditEvent
from offline_payment.audit.hashing import (
    domain_hash_leaf,
    domain_hash_node,
    domain_hash_leaf_hex,
)
from offline_payment.audit.proofs import MerkleProof, ProofStep

EMPTY_ROOT_BYTES: bytes = hashlib.sha256(b"").digest()


class MerkleTree:
    """Canonical Merkle Tree.

    Properties:
    - Leaves are domain-separated with 0x00.
    - Internal nodes are domain-separated with 0x01.
    - Odd-count levels duplicate the trailing node.
    - Stores all levels for deterministic proof generation in O(log N).
    """

    def __init__(self, leaves: Optional[Sequence[Union[AuditEvent, bytes, str]]] = None) -> None:
        self.raw_leaves: List[bytes] = []
        self.levels: List[List[bytes]] = []

        if leaves:
            for item in leaves:
                self.add_leaf(item)
            self.build()

    def add_leaf(self, item: Union[AuditEvent, bytes, str]) -> None:
        """Add a leaf before building the tree."""
        if isinstance(item, AuditEvent):
            leaf_hash = item.leaf_hash()
        elif isinstance(item, bytes):
            # If 32 bytes, assume already domain-leaf hashed; otherwise hash it
            if len(item) == 32:
                leaf_hash = item
            else:
                leaf_hash = domain_hash_leaf(item)
        elif isinstance(item, str):
            clean = item.removeprefix("0x")
            if len(clean) == 64:
                leaf_hash = bytes.fromhex(clean)
            else:
                leaf_hash = domain_hash_leaf(item.encode("utf-8"))
        else:
            raise TypeError(f"Unsupported leaf type: {type(item)}")

        self.raw_leaves.append(leaf_hash)

    def build(self) -> bytes:
        """Construct the Merkle tree and compute the root hash."""
        if not self.raw_leaves:
            self.levels = [[EMPTY_ROOT_BYTES]]
            return EMPTY_ROOT_BYTES

        current_level: List[bytes] = list(self.raw_leaves)
        self.levels = [current_level]

        while len(current_level) > 1:
            next_level: List[bytes] = []
            n = len(current_level)
            for i in range(0, n, 2):
                left = current_level[i]
                right = current_level[i + 1] if i + 1 < n else left
                parent = domain_hash_node(left, right)
                next_level.append(parent)
            self.levels.append(next_level)
            current_level = next_level

        return self.root_bytes

    @property
    def root_bytes(self) -> bytes:
        """Root hash as 32 raw bytes."""
        if not self.levels:
            return EMPTY_ROOT_BYTES
        return self.levels[-1][0]

    @property
    def root_hex(self) -> str:
        """Root hash as a 64-character hex string."""
        return self.root_bytes.hex()

    @property
    def leaf_count(self) -> int:
        """Number of leaves in the tree."""
        return len(self.raw_leaves)

    def get_leaf_hex(self, index: int) -> str:
        """Get the hex hash of the leaf at the given index."""
        if index < 0 or index >= len(self.raw_leaves):
            raise IndexError(f"Leaf index {index} out of range [0, {len(self.raw_leaves)})")
        return self.raw_leaves[index].hex()

    def generate_proof(self, leaf_index: int) -> MerkleProof:
        """Generate a Merkle inclusion proof for the leaf at leaf_index."""
        if not self.levels or not self.raw_leaves:
            raise ValueError("Cannot generate proof from an empty Merkle tree")
        if leaf_index < 0 or leaf_index >= len(self.raw_leaves):
            raise IndexError(f"Leaf index {leaf_index} out of range [0, {len(self.raw_leaves)})")

        audit_path: List[ProofStep] = []
        idx = leaf_index

        for level_idx in range(len(self.levels) - 1):
            level = self.levels[level_idx]
            n = len(level)

            if idx % 2 == 0:
                # idx is left child, sibling is on the right
                sibling_bytes = level[idx + 1] if idx + 1 < n else level[idx]
                audit_path.append(ProofStep(sibling_hash=sibling_bytes.hex(), is_left=False))
            else:
                # idx is right child, sibling is on the left
                sibling_bytes = level[idx - 1]
                audit_path.append(ProofStep(sibling_hash=sibling_bytes.hex(), is_left=True))

            idx = idx // 2

        return MerkleProof(
            leaf_index=leaf_index,
            leaf_hash=self.raw_leaves[leaf_index].hex(),
            root_hash=self.root_hex,
            audit_path=audit_path,
        )
