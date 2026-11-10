"""Tests for standalone independent audit verification command and failure modes."""

import pytest
from offline_payment.audit.events import AuditEvent, AuditEventType
from offline_payment.audit.merkle_tree import MerkleTree
from offline_payment.audit.proofs import MerkleProof, ProofStep
from offline_payment.audit.verify_cli import verify_audit_event
from offline_payment.blockchain.adapter import SimulatedEVMAdapter


@pytest.fixture
def sample_audit_setup():
    events = [
        AuditEvent.create(
            event_type=AuditEventType.CLAIM_INGESTED,
            sequence_number=1,
            payload={"tx_uuid": "tx_test_101", "amount_paise": 50000},
            event_id="evt_001",
        ),
        AuditEvent.create(
            event_type=AuditEventType.SETTLEMENT_ALLOCATED,
            sequence_number=2,
            payload={"tx_uuid": "tx_test_101", "paid_paise": 50000, "status": "SETTLED_FULL"},
            event_id="evt_002",
        ),
        AuditEvent.create(
            event_type=AuditEventType.BATCH_CLOSED,
            sequence_number=3,
            payload={"batch_id": "batch_cli_test", "total_payout": 50000},
            event_id="evt_003",
        ),
    ]
    tree = MerkleTree(events)
    batch_id = "batch_cli_test"
    adapter = SimulatedEVMAdapter()
    adapter.anchor_root(batch_id=batch_id, merkle_root=tree.root_hex)

    proof = tree.generate_proof(1)  # Proof for evt_002
    return events[1], proof, batch_id, adapter


def test_verify_cli_happy_path(sample_audit_setup):
    event, proof, batch_id, adapter = sample_audit_setup
    result = verify_audit_event(
        event_data=event,
        proof_data=proof,
        batch_id=batch_id,
        adapter=adapter,
    )
    assert result.is_valid is True
    assert result.step_1_event_loaded is True
    assert result.step_2_canonical_bytes_derived is True
    assert result.step_3_leaf_hash_recomputed is True
    assert result.step_4_leaf_matches_proof is True
    assert result.step_5_root_reconstructed is True
    assert result.step_6_blockchain_queried is True
    assert result.step_7_roots_matched is True
    assert len(result.errors) == 0


def test_verify_cli_modified_payload(sample_audit_setup):
    event, proof, batch_id, adapter = sample_audit_setup
    # Tamper with payload
    tampered_event = AuditEvent.create(
        event_type=event.event_type,
        sequence_number=event.sequence_number,
        payload={"tx_uuid": "tx_test_101", "paid_paise": 9999999, "status": "SETTLED_FULL"},
        event_id=event.event_id,
        timestamp=event.timestamp,
    )

    result = verify_audit_event(
        event_data=tampered_event,
        proof_data=proof,
        batch_id=batch_id,
        adapter=adapter,
    )
    assert result.is_valid is False
    assert result.step_4_leaf_matches_proof is False
    assert any("Step 4 Failed" in err for err in result.errors)


def test_verify_cli_incorrect_proof(sample_audit_setup):
    event, proof, batch_id, adapter = sample_audit_setup
    # Tamper with sibling in audit path
    tampered_path = [
        ProofStep(sibling_hash="1" * 64, is_left=step.is_left)
        for step in proof.audit_path
    ]
    corrupted_proof = MerkleProof(
        leaf_index=proof.leaf_index,
        leaf_hash=proof.leaf_hash,
        root_hash=proof.root_hash,
        audit_path=tampered_path,
    )

    result = verify_audit_event(
        event_data=event,
        proof_data=corrupted_proof,
        batch_id=batch_id,
        adapter=adapter,
    )
    assert result.is_valid is False
    assert result.step_5_root_reconstructed is False
    assert any("Step 5 Failed" in err for err in result.errors)


def test_verify_cli_unknown_batch(sample_audit_setup):
    event, proof, _, adapter = sample_audit_setup
    result = verify_audit_event(
        event_data=event,
        proof_data=proof,
        batch_id="batch_does_not_exist",
        adapter=adapter,
    )
    assert result.is_valid is False
    assert result.step_6_blockchain_queried is False
    assert any("not found on blockchain" in err for err in result.errors)


def test_verify_cli_unanchored_batch(sample_audit_setup):
    event, proof, _, _ = sample_audit_setup
    empty_adapter = SimulatedEVMAdapter()
    result = verify_audit_event(
        event_data=event,
        proof_data=proof,
        batch_id="batch_unanchored",
        adapter=empty_adapter,
    )
    assert result.is_valid is False
    assert result.step_7_roots_matched is False


def test_verify_cli_duplicate_submission(sample_audit_setup):
    _, _, batch_id, adapter = sample_audit_setup
    with pytest.raises(ValueError, match="already anchored"):
        adapter.anchor_root(batch_id=batch_id, merkle_root="2" * 64)
