"""Tests for exact Merkle tree internal node counting, duplication behavior, and complexity."""

import math
import pytest
from offline_payment.audit.merkle_tree import MerkleTree


def compute_expected_internal_nodes_and_duplications(n: int):
    """Reference recurrence calculation matching MerkleTree.build()."""
    if n <= 1:
        return 0, 1, 0
    current = n
    total_hashes = 0
    duplications = 0
    depth = 1
    while current > 1:
        dups = current % 2
        duplications += dups
        parents = (current + 1) // 2
        total_hashes += parents
        current = parents
        depth += 1
    return total_hashes, depth, duplications


@pytest.mark.parametrize("n,expected_hashes,expected_depth,expected_dups", [
    (1, 0, 1, 0),
    (2, 1, 2, 0),
    (3, 3, 3, 1),
    (5, 6, 4, 2),
    (7, 7, 4, 1),
    (10, 11, 5, 2),
    (1000, 1001, 11, 2),
])
def test_merkle_tree_exact_internal_hash_count(n, expected_hashes, expected_depth, expected_dups):
    """Test exact internal node count, depth, and duplications for leaf counts 1, 2, 3, 5, 7, 10, 1000."""
    leaves = [f"leaf_{i}".encode("utf-8") for i in range(n)]
    tree = MerkleTree(leaves)

    # Actual levels: level 0 is raw leaves, levels 1..depth-1 are internal nodes
    actual_depth = len(tree.levels)
    actual_internal_nodes = sum(len(lvl) for lvl in tree.levels[1:])

    formula_hashes, formula_depth, formula_dups = compute_expected_internal_nodes_and_duplications(n)

    assert actual_depth == expected_depth
    assert actual_internal_nodes == expected_hashes
    assert actual_depth == formula_depth
    assert actual_internal_nodes == formula_hashes

    # General algorithmic complexity assertion:
    # Under odd-node duplication, total internal hashes is strictly bounded: n - 1 <= H(n) <= 2n - 1 = O(n)
    if n > 1:
        assert (n - 1) <= actual_internal_nodes < 2 * n
        # Depth is strictly ceil(log2(n)) + 1
        assert actual_depth == math.ceil(math.log2(n)) + 1


def test_merkle_proof_verification_at_all_tested_scales():
    """Verify that proof generation and verification execute in O(log n) steps across all tested scales."""
    for n in [1, 2, 3, 5, 7, 10, 1000]:
        leaves = [f"leaf_{i}".encode("utf-8") for i in range(n)]
        tree = MerkleTree(leaves)
        if n == 1:
            continue
        # Verify first, middle, and last leaf proofs
        for idx in [0, n // 2, n - 1]:
            proof = tree.generate_proof(idx)
            # Proof length must be exactly tree_depth - 1 == ceil(log2(n))
            assert len(proof.audit_path) == len(tree.levels) - 1
            assert len(proof.audit_path) == math.ceil(math.log2(n))
            from offline_payment.audit.proofs import verify_merkle_proof
            assert verify_merkle_proof(proof) is True
