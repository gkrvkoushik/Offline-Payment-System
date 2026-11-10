"""Unit tests for First Claim Wins (FC) settlement algorithm."""

import pytest
from offline_payment.config import SettlementPolicy, SettlementStatus, ClaimType
from offline_payment.models.allowance import Allowance
from offline_payment.models.permit import Permit
from offline_payment.models.claim import Claim
from offline_payment.settlement.first_claim import FirstClaimSettlement


@pytest.fixture
def sample_setup():
    p1 = Permit(
        permit_id="p_1",
        allowance_id="alw_1",
        payer_id="payer_1",
        payer_public_key="pub_1",
        denomination=50000,
        settlement_deadline=1000,
        issuer_signature="sig_1",
    )
    p2 = Permit(
        permit_id="p_2",
        allowance_id="alw_1",
        payer_id="payer_1",
        payer_public_key="pub_1",
        denomination=50000,
        settlement_deadline=1000,
        issuer_signature="sig_2",
    )
    allowance = Allowance(
        allowance_id="alw_1",
        payer_id="payer_1",
        allowance_amount=50000,  # C = 500
        payer_hold=50000,        # H = 500
        issuer_guarantee=0,      # F = 0
        settlement_deadline=1000,
        permits=[p1, p2],
    )
    return allowance, p1, p2


def test_fc_single_permit_double_spend(sample_setup):
    allowance, p1, _ = sample_setup
    policy = FirstClaimSettlement()

    c1 = Claim(
        tx_uuid="tx_1",
        allowance_id="alw_1",
        permit_id="p_1",
        payer_id="payer_1",
        payee_id="mule_1",
        amount=50000,
        ingestion_sequence=1,
        submission_time=10,
        claim_type=ClaimType.MULE,
    )
    c2 = Claim(
        tx_uuid="tx_2",
        allowance_id="alw_1",
        permit_id="p_1",
        payer_id="payer_1",
        payee_id="merchant_a",
        amount=50000,
        ingestion_sequence=2,
        submission_time=11,
        claim_type=ClaimType.HONEST_MERCHANT,
    )
    c3 = Claim(
        tx_uuid="tx_3",
        allowance_id="alw_1",
        permit_id="p_1",
        payer_id="payer_1",
        payee_id="merchant_b",
        amount=50000,
        ingestion_sequence=3,
        submission_time=12,
        claim_type=ClaimType.HONEST_MERCHANT,
    )

    batch_res = policy.settle(allowance, [c2, c1, c3])  # Unsorted order input

    assert batch_res.policy == SettlementPolicy.FIRST_CLAIM
    assert batch_res.total_payout == 50000
    assert batch_res.total_eligible_count == 3

    # Check results in sorted ingestion sequence order
    r1, r2, r3 = batch_res.claim_results
    assert r1.claim.tx_uuid == "tx_1"
    assert r1.status == SettlementStatus.SETTLED_FULL
    assert r1.paid_amount == 50000
    assert r1.funded_from_c == 50000

    assert r2.claim.tx_uuid == "tx_2"
    assert r2.status == SettlementStatus.REJECTED
    assert r2.paid_amount == 0

    assert r3.claim.tx_uuid == "tx_3"
    assert r3.status == SettlementStatus.REJECTED
    assert r3.paid_amount == 0


def test_fc_two_unique_permits(sample_setup):
    allowance, p1, p2 = sample_setup
    policy = FirstClaimSettlement()

    c1 = Claim(
        tx_uuid="tx_1",
        allowance_id="alw_1",
        permit_id="p_1",
        payer_id="payer_1",
        payee_id="m_1",
        amount=50000,
        ingestion_sequence=1,
        submission_time=10,
    )
    c2 = Claim(
        tx_uuid="tx_2",
        allowance_id="alw_1",
        permit_id="p_2",
        payer_id="payer_1",
        payee_id="m_2",
        amount=50000,
        ingestion_sequence=2,
        submission_time=11,
    )

    batch_res = policy.settle(allowance, [c1, c2])
    assert batch_res.total_payout == 100000
    assert batch_res.claim_results[0].paid_amount == 50000
    assert batch_res.claim_results[1].paid_amount == 50000
