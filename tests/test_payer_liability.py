"""Unit tests for Payer-Liable Strict Prefix (PL) settlement algorithm."""

import pytest
from offline_payment.config import SettlementPolicy, SettlementStatus, ClaimType
from offline_payment.models.allowance import Allowance
from offline_payment.models.permit import Permit
from offline_payment.models.claim import Claim
from offline_payment.settlement.payer_liability import PayerLiabilitySettlement


@pytest.fixture
def sample_allowance():
    p = Permit(
        permit_id="p_1",
        allowance_id="alw_1",
        payer_id="payer_1",
        payer_public_key="pub_1",
        denomination=50000,
        settlement_deadline=1000,
        issuer_signature="sig_1",
    )
    return Allowance(
        allowance_id="alw_1",
        payer_id="payer_1",
        allowance_amount=50000,  # C = ₹500
        payer_hold=50000,        # H = ₹500
        issuer_guarantee=0,      # F = 0
        settlement_deadline=1000,
        permits=[p],
    )


def test_pl_exact_initial_scenario(sample_allowance):
    """Initial reproducible scenario under PL:

    Claim 1 (Mule): ₹500 -> Paid ₹500 from C
    Claim 2 (Merchant A): ₹500 -> Paid ₹500 from H
    Claim 3 (Merchant B): ₹500 -> ₹0 (Halted due to reserve exhaustion)
    Total payout: ₹1000
    """
    policy = PayerLiabilitySettlement()

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

    batch_res = policy.settle(sample_allowance, [c1, c2, c3])

    assert batch_res.policy == SettlementPolicy.PAYER_LIABILITY
    assert batch_res.total_payout == 100000

    r1, r2, r3 = batch_res.claim_results
    assert r1.paid_amount == 50000
    assert r1.status == SettlementStatus.SETTLED_FULL
    assert r1.funded_from_c == 50000
    assert r1.funded_from_h == 0

    assert r2.paid_amount == 50000
    assert r2.status == SettlementStatus.SETTLED_FULL
    assert r2.funded_from_c == 0
    assert r2.funded_from_h == 50000

    assert r3.paid_amount == 0
    assert r3.status == SettlementStatus.UNPAID
    assert "Insufficient remaining reserve" in r3.rejection_reason


def test_pl_strict_prefix_halting_with_smaller_subsequent_claim():
    """Even if a later claim is small enough to fit the remaining reserve,

    PL MUST NOT pay it if an earlier claim could not be paid in full.
    """
    p = Permit(
        permit_id="p_1",
        allowance_id="alw_1",
        payer_id="payer_1",
        payer_public_key="pub_1",
        denomination=50000,
        settlement_deadline=1000,
        issuer_signature="sig_1",
    )
    # Total reserve = 60000
    allowance = Allowance(
        allowance_id="alw_1",
        payer_id="payer_1",
        allowance_amount=60000,
        payer_hold=0,
        issuer_guarantee=0,
        settlement_deadline=1000,
        permits=[p],
    )
    policy = PayerLiabilitySettlement()

    # Claim 1: 40000 -> fits (leaves 20000)
    c1 = Claim(
        tx_uuid="tx_1",
        allowance_id="alw_1",
        permit_id="p_1",
        payer_id="payer_1",
        payee_id="m1",
        amount=40000,
        ingestion_sequence=1,
        submission_time=10,
    )
    # Claim 2: 30000 -> does not fit (only 20000 left) -> halts!
    c2 = Claim(
        tx_uuid="tx_2",
        allowance_id="alw_1",
        permit_id="p_1",
        payer_id="payer_1",
        payee_id="m2",
        amount=30000,
        ingestion_sequence=2,
        submission_time=11,
    )
    # Claim 3: 10000 -> would fit remaining 20000, but prefix halted, so MUST NOT be paid!
    c3 = Claim(
        tx_uuid="tx_3",
        allowance_id="alw_1",
        permit_id="p_1",
        payer_id="payer_1",
        payee_id="m3",
        amount=10000,
        ingestion_sequence=3,
        submission_time=12,
    )

    batch_res = policy.settle(allowance, [c1, c2, c3])
    r1, r2, r3 = batch_res.claim_results

    assert r1.paid_amount == 40000
    assert r1.status == SettlementStatus.SETTLED_FULL

    assert r2.paid_amount == 0
    assert r2.status == SettlementStatus.UNPAID

    assert r3.paid_amount == 0
    assert r3.status == SettlementStatus.UNPAID
    assert "halted" in r3.rejection_reason.lower()

    # Total payout is strictly 40000, remaining 20000 is unspent
    assert batch_res.total_payout == 40000
    assert batch_res.remaining_reserve == 20000
