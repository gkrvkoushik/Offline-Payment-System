"""Unit tests for MerkleTree generation, root derivation, and inclusion proofs."""

import pytest
from offline_payment.audit.events import AuditEvent, AuditEventType
from offline_payment.audit.merkle_tree import MerkleTree, EMPTY_ROOT_BYTES
from offline_payment.audit.proofs import MerkleProof, ProofStep, verify_merkle_proof


def test_empty_merkle_tree():
    tree = MerkleTree()
    assert tree.root_bytes == EMPTY_ROOT_BYTES
    assert len(tree.root_hex) == 64
    assert tree.leaf_count == 0

    with pytest.raises(ValueError, match="Cannot generate proof from an empty"):
        tree.generate_proof(0)


def test_single_leaf_merkle_tree():
    leaf_data = b"only_one_transaction"
    tree = MerkleTree([leaf_data])
    assert tree.leaf_count == 1
    # For a single leaf, root equals the leaf hash
    assert tree.root_hex == tree.get_leaf_hex(0)

    proof = tree.generate_proof(0)
    assert proof.leaf_index == 0
    assert proof.audit_path == []
    assert verify_merkle_proof(proof) is True


def test_two_leaf_merkle_tree():
    leaf_a = b"transaction_alpha"
    leaf_b = b"transaction_beta"
    tree = MerkleTree([leaf_a, leaf_b])
    assert tree.leaf_count == 2

    # Proof for leaf 0
    proof_0 = tree.generate_proof(0)
    assert proof_0.leaf_index == 0
    assert len(proof_0.audit_path) == 1
    assert proof_0.audit_path[0].is_left is False
    assert proof_0.audit_path[0].sibling_hash == tree.get_leaf_hex(1)
    assert verify_merkle_proof(proof_0) is True

    # Proof for leaf 1
    proof_1 = tree.generate_proof(1)
    assert proof_1.leaf_index == 1
    assert len(proof_1.audit_path) == 1
    assert proof_1.audit_path[0].is_left is True
    assert proof_1.audit_path[0].sibling_hash == tree.get_leaf_hex(0)
    assert verify_merkle_proof(proof_1) is True


def test_odd_leaves_merkle_tree():
    # 3 leaves tests odd-count duplication at level 0
    leaves = [b"leaf_1", b"leaf_2", b"leaf_3"]
    tree = MerkleTree(leaves)
    assert tree.leaf_count == 3

    for i in range(3):
        proof = tree.generate_proof(i)
        assert proof.leaf_index == i
        assert verify_merkle_proof(proof) is True


@pytest.mark.parametrize("leaf_count", [4, 5, 7, 8, 15, 16, 33])
def test_various_size_merkle_trees(leaf_count):
    events = [
        AuditEvent.create(
            event_type=AuditEventType.CLAIM_INGESTED,
            sequence_number=i + 1,
            payload={"tx_index": i, "amount": (i + 1) * 100},
        )
        for i in range(leaf_count)
    ]
    tree = MerkleTree(events)
    assert tree.leaf_count == leaf_count

    for i in range(leaf_count):
        proof = tree.generate_proof(i)
        assert proof.leaf_index == i
        assert verify_merkle_proof(proof) is True


def test_proof_tampering_detection():
    tree = MerkleTree([b"item_1", b"item_2", b"item_3", b"item_4"])
    proof = tree.generate_proof(1)
    assert verify_merkle_proof(proof) is True

    # Tamper with leaf hash
    corrupted_leaf = MerkleProof(
        leaf_index=proof.leaf_index,
        leaf_hash="0" * 64,
        root_hash=proof.root_hash,
        audit_path=proof.audit_path,
    )
    assert verify_merkle_proof(corrupted_leaf) is False

    # Tamper with root hash
    corrupted_root = MerkleProof(
        leaf_index=proof.leaf_index,
        leaf_hash=proof.leaf_hash,
        root_hash="f" * 64,
        audit_path=proof.audit_path,
    )
    assert verify_merkle_proof(corrupted_root) is False

    # Tamper with sibling in audit path
    corrupted_path = [
        ProofStep(sibling_hash="a" * 64, is_left=step.is_left)
        for step in proof.audit_path
    ]
    corrupted_sibling = MerkleProof(
        leaf_index=proof.leaf_index,
        leaf_hash=proof.leaf_hash,
        root_hash=proof.root_hash,
        audit_path=corrupted_path,
    )
    assert verify_merkle_proof(corrupted_sibling) is False

    # Tamper with direction
    flipped_direction_path = [
        ProofStep(sibling_hash=proof.audit_path[0].sibling_hash, is_left=not proof.audit_path[0].is_left)
    ] + proof.audit_path[1:]
    corrupted_dir = MerkleProof(
        leaf_index=proof.leaf_index,
        leaf_hash=proof.leaf_hash,
        root_hash=proof.root_hash,
        audit_path=flipped_direction_path,
    )
    assert verify_merkle_proof(corrupted_dir) is False


def test_merkle_proof_serialization_roundtrip():
    tree = MerkleTree([b"alpha", b"beta", b"gamma"])
    proof = tree.generate_proof(2)

    data = proof.to_dict()
    restored = MerkleProof.from_dict(data)

    assert restored.leaf_index == proof.leaf_index
    assert restored.leaf_hash == proof.leaf_hash
    assert restored.root_hash == proof.root_hash
    assert len(restored.audit_path) == len(proof.audit_path)
    assert verify_merkle_proof(restored) is True
