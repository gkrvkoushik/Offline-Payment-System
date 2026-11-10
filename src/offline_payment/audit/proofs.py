"""Merkle inclusion proof structure and verification algorithms."""

from dataclasses import dataclass, asdict
from typing import Any, Dict, List
from offline_payment.audit.hashing import domain_hash_node


@dataclass
class ProofStep:
    """A single step in a Merkle inclusion proof path."""
    sibling_hash: str  # 64-char hex string
    is_left: bool      # True if sibling is on the left, False if on the right


@dataclass
class MerkleProof:
    """Cryptographic proof of membership in an anchored Merkle tree."""
    leaf_index: int
    leaf_hash: str     # 64-char hex string
    root_hash: str     # 64-char hex string
    audit_path: List[ProofStep]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "leaf_index": self.leaf_index,
            "leaf_hash": self.leaf_hash,
            "root_hash": self.root_hash,
            "audit_path": [asdict(step) for step in self.audit_path],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MerkleProof":
        return cls(
            leaf_index=data["leaf_index"],
            leaf_hash=data["leaf_hash"],
            root_hash=data["root_hash"],
            audit_path=[
                ProofStep(
                    sibling_hash=step["sibling_hash"],
                    is_left=step["is_left"],
                )
                for step in data["audit_path"]
            ],
        )

    def verify(self) -> bool:
        """Verify that this proof correctly derives root_hash from leaf_hash."""
        return verify_merkle_proof(self)


def verify_merkle_proof(proof: MerkleProof) -> bool:
    """Independently verify a Merkle inclusion proof using domain-separated node hashing.

    Returns True if deriving the path matches proof.root_hash, False otherwise.
    """
    try:
        current = bytes.fromhex(proof.leaf_hash.removeprefix("0x"))
        expected_root = bytes.fromhex(proof.root_hash.removeprefix("0x"))

        for step in proof.audit_path:
            sibling = bytes.fromhex(step.sibling_hash.removeprefix("0x"))
            if step.is_left:
                current = domain_hash_node(sibling, current)
            else:
                current = domain_hash_node(current, sibling)

        return current == expected_root
    except Exception:
        return False
