"""Unit tests for Global Pro-Rata (PR) settlement algorithm."""

import pytest
from offline_payment.config import SettlementPolicy, SettlementStatus, ClaimType
from offline_payment.models.allowance import Allowance
from offline_payment.models.permit import Permit
from offline_payment.models.claim import Claim
from offline_payment.settlement.pro_rata import GlobalProRataSettlement


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


def test_pro_rata_exact_initial_scenario(sample_allowance):
    """Initial reproducible scenario: S = 100000, 3 claims of 50000 each.

    Expected payouts: 33334, 33333, 33333 paise (₹333.34, ₹333.33, ₹333.33).
    """
    policy = GlobalProRataSettlement()

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

    assert batch_res.policy == SettlementPolicy.GLOBAL_PRO_RATA
    assert batch_res.total_payout == 100000  # Total reserve fully allocated
    assert batch_res.remaining_reserve == 0

    r1, r2, r3 = batch_res.claim_results
    assert r1.paid_amount == 33334  # Earliest ingestion sequence receives the 1 paise tie-breaker
    assert r2.paid_amount == 33333
    assert r3.paid_amount == 33333

    assert r1.status == SettlementStatus.SETTLED_PARTIAL
    assert r2.status == SettlementStatus.SETTLED_PARTIAL
    assert r3.status == SettlementStatus.SETTLED_PARTIAL

    # Check total funding tiers conservation
    assert batch_res.total_funded_c == 50000
    assert batch_res.total_funded_h == 50000
    assert batch_res.total_funded_f == 0


def test_pro_rata_full_coverage(sample_allowance):
    policy = GlobalProRataSettlement()
    c1 = Claim(
        tx_uuid="tx_1",
        allowance_id="alw_1",
        permit_id="p_1",
        payer_id="payer_1",
        payee_id="m1",
        amount=20000,
        ingestion_sequence=1,
        submission_time=10,
    )
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

    batch_res = policy.settle(sample_allowance, [c1, c2])
    assert batch_res.total_payout == 50000
    assert batch_res.claim_results[0].paid_amount == 20000
    assert batch_res.claim_results[0].status == SettlementStatus.SETTLED_FULL
    assert batch_res.claim_results[1].paid_amount == 30000
    assert batch_res.claim_results[1].status == SettlementStatus.SETTLED_FULL
    assert batch_res.remaining_reserve == 50000
