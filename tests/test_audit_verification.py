"""End-to-end integration tests for audit pipeline, blockchain anchoring, and verification."""

import pytest
from offline_payment.audit import (
    AuditEvent,
    AuditSettlementPipeline,
    IndependentAuditVerifier,
    AuditEventType,
)
from offline_payment.blockchain import SimulatedEVMAdapter, AnchorQueueManager
from offline_payment.config import ClaimType
from offline_payment.models.account import Account
from offline_payment.models.allowance import Allowance
from offline_payment.models.claim import Claim
from offline_payment.models.permit import Permit
from offline_payment.settlement.first_claim import FirstClaimSettlement
from offline_payment.settlement.pro_rata import GlobalProRataSettlement
from offline_payment.settlement.payer_liability import PayerLiabilitySettlement


@pytest.fixture
def test_setup():
    allowance = Allowance(
        allowance_id="alw_audit_test",
        payer_id="payer_alice",
        allowance_amount=50000,   # C = INR 500
        payer_hold=50000,         # H = INR 500
        issuer_guarantee=0,       # F = INR 0
        settlement_deadline=1800000000,
    )
    p1 = Permit(
        permit_id="pmt_01",
        allowance_id="alw_audit_test",
        payer_id="payer_alice",
        payer_public_key="pub_alice",
        denomination=50000,
        settlement_deadline=1800000000,
        issuer_signature="sig_issuer",
    )
    allowance.permits = [p1]

    # Double spend scenario: 1 permit presented to 3 merchants (1 mule, 2 honest)
    claims = [
        Claim(
            tx_uuid="tx_mule",
            allowance_id="alw_audit_test",
            permit_id="pmt_01",
            payer_id="payer_alice",
            payee_id="mule_bob",
            amount=50000,
            ingestion_sequence=1,
            submission_time=1700000000,
            claim_type=ClaimType.MULE,
            offline_accepted=True,
        ),
        Claim(
            tx_uuid="tx_honest_a",
            allowance_id="alw_audit_test",
            permit_id="pmt_01",
            payer_id="payer_alice",
            payee_id="merchant_a",
            amount=50000,
            ingestion_sequence=2,
            submission_time=1700000001,
            claim_type=ClaimType.HONEST_MERCHANT,
            offline_accepted=True,
        ),
        Claim(
            tx_uuid="tx_honest_b",
            allowance_id="alw_audit_test",
            permit_id="pmt_01",
            payer_id="payer_alice",
            payee_id="merchant_b",
            amount=50000,
            ingestion_sequence=3,
            submission_time=1700000002,
            claim_type=ClaimType.HONEST_MERCHANT,
            offline_accepted=True,
        ),
    ]

    adapter = SimulatedEVMAdapter()
    return allowance, claims, adapter


@pytest.mark.parametrize("policy_cls", [FirstClaimSettlement, GlobalProRataSettlement, PayerLiabilitySettlement])
def test_end_to_end_settle_anchor_and_verify(test_setup, policy_cls):
    allowance, claims, adapter = test_setup
    policy = policy_cls()
    batch_result = policy.settle(allowance, claims)
    batch_id = f"batch_{policy.policy_type.value}_001"

    # 1. Generate canonical audit trail & Merkle tree
    tree, events = AuditSettlementPipeline.generate_batch_audit_trail(
        batch_id=batch_id,
        allowance=allowance,
        claims=claims,
        batch_result=batch_result,
    )
    assert tree.leaf_count == len(events)
    assert tree.root_hex is not None

    # 2. Anchor root on blockchain
    receipt = adapter.anchor_root(batch_id=batch_id, merkle_root=tree.root_hex)
    assert receipt.status == "SUCCESS"

    # 3. Verify single claim inclusion proof
    proof = AuditSettlementPipeline.get_claim_proof("tx_honest_a", events, tree)
    assert proof is not None
    assert IndependentAuditVerifier.verify_claim_inclusion_against_anchor(adapter, batch_id, proof) is True

    # 4. Independent batch verification & conservation of funds check
    report = IndependentAuditVerifier.verify_batch_audit_trail(adapter, batch_id, events, allowance)
    assert report.is_valid is True
    assert report.root_matched_on_chain is True
    assert report.merkle_tree_verified is True
    assert report.conservation_of_funds_valid is True
    assert report.monotonic_sequence_valid is True
    assert report.total_claims_verified == len(claims)
    assert report.total_paid_paise == batch_result.total_payout
    assert len(report.errors) == 0


def test_independent_verifier_detects_tampering(test_setup):
    allowance, claims, adapter = test_setup
    policy = PayerLiabilitySettlement()
    batch_result = policy.settle(allowance, claims)
    batch_id = "batch_tamper_test"

    tree, events = AuditSettlementPipeline.generate_batch_audit_trail(
        batch_id=batch_id,
        allowance=allowance,
        claims=claims,
        batch_result=batch_result,
    )
    adapter.anchor_root(batch_id=batch_id, merkle_root=tree.root_hex)

    # Tamper with an event: change a payout amount
    tampered_events = [
        AuditEvent.create(
            event_type=e.event_type,
            sequence_number=e.sequence_number,
            payload=dict(e.payload),
            timestamp=e.timestamp,
            event_id=e.event_id,
        )
        for e in events
    ]
    # Inflate payout of honest merchant
    for e in tampered_events:
        if e.event_type == AuditEventType.SETTLEMENT_ALLOCATED and e.payload.get("tx_uuid") == "tx_honest_a":
            e.payload["paid_paise"] = 9999999  # Massive inflation

    report = IndependentAuditVerifier.verify_batch_audit_trail(adapter, batch_id, tampered_events, allowance)
    assert report.is_valid is False
    assert report.root_matched_on_chain is False
    assert len(report.errors) > 0


def test_independent_verifier_detects_unanchored_batch(test_setup):
    allowance, claims, adapter = test_setup
    tree, events = AuditSettlementPipeline.generate_batch_audit_trail(
        batch_id="batch_unanchored",
        allowance=allowance,
        claims=claims,
        batch_result=FirstClaimSettlement().settle(allowance, claims),
    )
    # Do NOT anchor to adapter
    report = IndependentAuditVerifier.verify_batch_audit_trail(adapter, "batch_unanchored", events, allowance)
    assert report.is_valid is False
    assert report.root_matched_on_chain is False
    assert "not found on blockchain" in report.errors[0]
