"""Comprehensive integration and security tests for PaymentAuditAnchor on a real Hardhat EVM node."""

import pytest
from web3 import Web3

from offline_payment.audit.canonicalization import canonicalize
from offline_payment.audit.events import AuditEvent, AuditEventType
from offline_payment.audit.hashing import domain_hash_leaf_hex, domain_hash_node
from offline_payment.audit.proofs import MerkleProof, ProofStep
from offline_payment.audit.verify_cli import verify_audit_event
from offline_payment.blockchain.compiler import compile_anchor_contract
from offline_payment.blockchain.local_node_adapter import EthereumLocalNodeAdapter
from offline_payment.blockchain.anchor_service import AnchorQueueManager, AnchorTaskStatus
from offline_payment.blockchain.environments import ENV_REAL_LOCAL_HARDHAT_EVM


@pytest.fixture(scope="module")
def local_adapter():
    """Module-level fixture providing connected EthereumLocalNodeAdapter."""
    try:
        adapter = EthereumLocalNodeAdapter()
        return adapter
    except Exception as e:
        pytest.skip(f"Local Hardhat EVM node is not running on 127.0.0.1:8545: {e}")


def test_real_evm_deployment_and_bytecode(local_adapter):
    """Verify that contract is deployed to a genuine 20-byte address with non-empty EVM bytecode."""
    assert Web3.is_address(local_adapter.contract_address)
    code = local_adapter.w3.eth.get_code(Web3.to_checksum_address(local_adapter.contract_address))
    assert len(code) > 100
    assert local_adapter.execution_environment == ENV_REAL_LOCAL_HARDHAT_EVM


def test_real_evm_anchor_batch_success(local_adapter):
    """Verify successful batch anchoring on real EVM with authentic transaction receipt and block timestamp."""
    batch_id = f"batch_real_test_{local_adapter.w3.eth.block_number}"
    merkle_root = "0x" + "a1b2c3d4e5f60718293a4b5c6d7e8f90" * 2
    metadata_hash = "0x" + "f" * 64

    receipt = local_adapter.anchor_root(
        batch_id=batch_id,
        merkle_root=merkle_root,
        metadata_hash=metadata_hash,
    )

    assert receipt.batch_id == batch_id
    assert receipt.merkle_root == merkle_root.removeprefix("0x").lower()
    assert receipt.tx_hash.startswith("0x") or len(receipt.tx_hash) == 64
    assert receipt.block_number > 0
    assert receipt.block_timestamp > 0
    assert receipt.gas_used > 21000  # Genuine EVM gas measurement
    assert receipt.execution_environment == ENV_REAL_LOCAL_HARDHAT_EVM
    assert receipt.receipt_status == "REAL_LOCAL_EVM_MINED"

    # Query getAnchor contract state
    onchain = local_adapter.get_anchor(batch_id)
    assert onchain is not None
    assert onchain.merkle_root.lower() == merkle_root.removeprefix("0x").lower()
    assert onchain.block_timestamp == receipt.block_timestamp


def test_real_evm_duplicate_batch_rejection(local_adapter):
    """Verify that attempting to re-anchor the exact same batch ID reverts on-chain (BatchAlreadyExists)."""
    batch_id = f"batch_dup_test_{local_adapter.w3.eth.block_number}"
    merkle_root = "0x" + "11" * 32

    # First anchoring succeeds
    local_adapter.anchor_root(batch_id=batch_id, merkle_root=merkle_root)

    # Second anchoring MUST fail on-chain
    with pytest.raises(Exception) as exc_info:
        local_adapter.anchor_root(batch_id=batch_id, merkle_root=merkle_root)
    err = str(exc_info.value).lower()
    assert "batchalreadyexists" in err or "revert" in err or "reverted" in err


def test_real_evm_unauthorized_submitter_rejected(local_adapter):
    """Verify that an unauthorized address cannot call anchorBatch."""
    unauthorized_account = local_adapter.w3.eth.accounts[5]
    batch_id = f"batch_unauth_{local_adapter.w3.eth.block_number}"
    merkle_root = "0x" + "22" * 32

    with pytest.raises(Exception) as exc_info:
        local_adapter.anchor_root(
            batch_id=batch_id,
            merkle_root=merkle_root,
            submitter=unauthorized_account,
        )
    err = str(exc_info.value).lower()
    assert "unauthorizedcaller" in err or "revert" in err or "reverted" in err


def test_real_evm_merkle_inclusion_verification(local_adapter):
    """Verify that EVM smart contract method verifyInclusion executes SHA-256 precompile checks correctly."""
    # Build two audit events
    event1 = AuditEvent.create(AuditEventType.CLAIM_INGESTED, sequence_number=1, payload={"claim_id": "c1", "amt": 100})
    event2 = AuditEvent.create(AuditEventType.VALIDATION_EVALUATED, sequence_number=2, payload={"claim_id": "c2", "amt": 200})

    leaf1 = bytes.fromhex(domain_hash_leaf_hex(event1.canonical_bytes()))
    leaf2 = bytes.fromhex(domain_hash_leaf_hex(event2.canonical_bytes()))

    root = domain_hash_node(leaf1, leaf2)
    root_hex = root.hex()

    batch_id = f"batch_inclusion_{local_adapter.w3.eth.block_number}"
    local_adapter.anchor_root(batch_id=batch_id, merkle_root=root_hex)

    # Valid proof for event1 (leaf2 is right sibling)
    is_valid = local_adapter.verify_inclusion_on_chain(
        batch_id=batch_id,
        leaf_hash=leaf1.hex(),
        proof=[leaf2.hex()],
        is_left=[False],
    )
    assert is_valid is True

    # Invalid sibling should fail
    bogus_sibling = "0x" + "ff" * 32
    is_invalid = local_adapter.verify_inclusion_on_chain(
        batch_id=batch_id,
        leaf_hash=leaf1.hex(),
        proof=[bogus_sibling],
        is_left=[False],
    )
    assert is_invalid is False


def test_real_evm_independent_audit_verifier(local_adapter):
    """Execute full 10-step independent audit verifier against real EVM contract."""
    event = AuditEvent.create(AuditEventType.CLAIM_INGESTED, sequence_number=1, payload={"tx": "off1", "val": 500})
    leaf_bytes = bytes.fromhex(domain_hash_leaf_hex(event.canonical_bytes()))
    sibling_bytes = bytes.fromhex("dd" * 32)
    root_bytes = domain_hash_node(leaf_bytes, sibling_bytes)

    batch_id = f"batch_verify_10_{local_adapter.w3.eth.block_number}"
    local_adapter.anchor_root(batch_id=batch_id, merkle_root=root_bytes.hex())

    proof = MerkleProof(
        leaf_index=0,
        leaf_hash=leaf_bytes.hex(),
        root_hash=root_bytes.hex(),
        audit_path=[ProofStep(sibling_hash=sibling_bytes.hex(), is_left=False)],
    )

    result = verify_audit_event(
        event_data=event,
        proof_data=proof,
        batch_id=batch_id,
        adapter=local_adapter,
    )

    assert result.is_valid is True
    assert result.step_1_event_loaded is True
    assert result.step_2_canonical_bytes_derived is True
    assert result.step_3_leaf_hash_recomputed is True
    assert result.step_4_leaf_matches_proof is True
    assert result.step_5_root_reconstructed is True
    assert result.step_6_contract_inclusion_verified is True
    assert result.step_7_blockchain_queried is True
    assert result.step_8_roots_matched is True
    assert len(result.errors) == 0


def test_real_evm_sqlite_queue_reconciliation(local_adapter, tmp_path):
    """Verify SQLite queue idempotency and timeout reconciliation against real EVM."""
    db_file = str(tmp_path / "test_tasks.db")
    queue_mgr = AnchorQueueManager(adapter=local_adapter, db_path=db_file)

    batch_id = f"batch_queue_{local_adapter.w3.eth.block_number}"
    merkle_root = "0x" + "33" * 32

    # Enqueue and process
    task = queue_mgr.enqueue_batch(batch_id, merkle_root)
    assert task.status == AnchorTaskStatus.QUEUED

    queue_mgr.process_task(task)
    assert task.status == AnchorTaskStatus.ANCHORED
    assert task.receipt is not None
    assert task.receipt.execution_environment == ENV_REAL_LOCAL_HARDHAT_EVM

    # Enqueue same batch ID with conflicting root must raise ValueError
    with pytest.raises(ValueError) as exc:
        queue_mgr.enqueue_batch(batch_id, "0x" + "44" * 32)
    assert "ConflictingBatchRegistration" in str(exc.value)

    # Process restart recovery test
    recovered_mgr = AnchorQueueManager(adapter=local_adapter, db_path=db_file)
    recovered_task = recovered_mgr.get_task(batch_id)
    assert recovered_task is not None
    assert recovered_task.status == AnchorTaskStatus.ANCHORED
    assert recovered_task.receipt.merkle_root == merkle_root.removeprefix("0x").lower()
