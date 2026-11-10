"""Comprehensive correctness invariant tests for the offline payment simulator."""

import pytest
from offline_payment.config import ClaimType, SettlementStatus
from offline_payment.models.account import Account
from offline_payment.models.allowance import Allowance
from offline_payment.models.permit import Permit
from offline_payment.models.claim import Claim
from offline_payment.settlement.first_claim import FirstClaimSettlement
from offline_payment.settlement.pro_rata import GlobalProRataSettlement
from offline_payment.settlement.payer_liability import PayerLiabilitySettlement


@pytest.fixture
def policies():
    return [
        FirstClaimSettlement(),
        GlobalProRataSettlement(),
        PayerLiabilitySettlement(),
    ]


@pytest.fixture
def standard_allowance():
    p1 = Permit("p_1", "alw_inv", "payer_1", "pk_1", 50000, 1000, "sig_1")
    p2 = Permit("p_2", "alw_inv", "payer_1", "pk_1", 50000, 1000, "sig_2")
    p3 = Permit("p_3", "alw_inv", "payer_1", "pk_1", 50000, 1000, "sig_3")
    return Allowance(
        allowance_id="alw_inv",
        payer_id="payer_1",
        allowance_amount=60000,  # C
        payer_hold=30000,        # H
        issuer_guarantee=10000,  # F
        settlement_deadline=1000,
        permits=[p1, p2, p3],
    )


# Invariant 1: Total payout never exceeds total reserve
def test_invariant_1_total_payout_never_exceeds_total_reserve(policies, standard_allowance):
    # Massive claim batch of 50000 * 5 = 250000 against reserve 100000
    claims = [
        Claim(f"tx_{i}", "alw_inv", f"p_{min(i, 3)}", "payer_1", f"m_{i}", 50000, i, 1000 + i)
        for i in range(1, 6)
    ]
    for policy in policies:
        res = policy.settle(standard_allowance, claims)
        assert res.total_payout <= standard_allowance.total_reserve, f"Failed for {policy.policy_type}"
        assert res.remaining_reserve >= 0


# Invariant 2: No claim receives a negative payout
def test_invariant_2_no_claim_receives_negative_payout(policies, standard_allowance):
    claims = [
        Claim("tx_1", "alw_inv", "p_1", "payer_1", "m_1", 50000, 1, 1001),
        Claim("tx_2", "alw_inv", "p_2", "payer_1", "m_2", 30000, 2, 1002),
    ]
    for policy in policies:
        res = policy.settle(standard_allowance, claims)
        for cr in res.claim_results:
            assert cr.paid_amount >= 0, f"Negative payout in {policy.policy_type}"
            assert cr.funded_from_c >= 0
            assert cr.funded_from_h >= 0
            assert cr.funded_from_f >= 0


# Invariant 3: No claim receives more than its requested amount
def test_invariant_3_no_claim_receives_more_than_requested(policies, standard_allowance):
    claims = [
        Claim("tx_1", "alw_inv", "p_1", "payer_1", "m_1", 25000, 1, 1001),
        Claim("tx_2", "alw_inv", "p_2", "payer_1", "m_2", 15000, 2, 1002),
    ]
    for policy in policies:
        res = policy.settle(standard_allowance, claims)
        for cr in res.claim_results:
            assert cr.paid_amount <= cr.requested_amount, f"Overpaid in {policy.policy_type}"


# Invariant 4: FC pays at most one claim per permit
def test_invariant_4_fc_pays_at_most_one_claim_per_permit(standard_allowance):
    policy = FirstClaimSettlement()
    claims = [
        Claim("tx_1", "alw_inv", "p_1", "payer_1", "m_1", 20000, 1, 1001),
        Claim("tx_2", "alw_inv", "p_1", "payer_1", "m_2", 20000, 2, 1002),
        Claim("tx_3", "alw_inv", "p_1", "payer_1", "m_3", 20000, 3, 1003),
    ]
    res = policy.settle(standard_allowance, claims)
    paid_claims = [cr for cr in res.claim_results if cr.paid_amount > 0]
    assert len(paid_claims) == 1
    assert paid_claims[0].claim.tx_uuid == "tx_1"


# Invariant 5: PR distributes reserve proportionally, subject to integer rounding
def test_invariant_5_pr_distributes_proportionally_with_integer_rounding(standard_allowance):
    policy = GlobalProRataSettlement()
    # 2 claims of 50000 each = 100000, Reserve S = 100000 -> full 1:1
    c1 = Claim("tx_1", "alw_inv", "p_1", "payer_1", "m_1", 50000, 1, 1001)
    c2 = Claim("tx_2", "alw_inv", "p_2", "payer_1", "m_2", 50000, 2, 1002)
    res = policy.settle(standard_allowance, [c1, c2])
    assert res.claim_results[0].paid_amount == 50000
    assert res.claim_results[1].paid_amount == 50000


# Invariant 6: PL follows strict ingestion-order prefix allocation
def test_invariant_6_pl_follows_strict_ingestion_order_prefix(standard_allowance):
    policy = PayerLiabilitySettlement()
    # Reserve S = 100000
    # c1 = 70000, c2 = 40000, c3 = 10000
    # c1 is paid (70000), leaving 30000. c2 needs 40000, cannot be paid in full -> halted!
    # c3 needs 10000, would fit 30000, but MUST be UNPAID!
    c1 = Claim("tx_1", "alw_inv", "p_1", "payer_1", "m_1", 70000, 1, 1001)  # permit denomination override
    p_big = Permit("p_big", "alw_inv", "payer_1", "pk_1", 100000, 1000, "sig")
    standard_allowance.permits.append(p_big)
    c1.permit_id = "p_big"
    c2 = Claim("tx_2", "alw_inv", "p_big", "payer_1", "m_2", 40000, 2, 1002)
    c3 = Claim("tx_3", "alw_inv", "p_big", "payer_1", "m_3", 10000, 3, 1003)

    res = policy.settle(standard_allowance, [c1, c2, c3])
    assert res.claim_results[0].paid_amount == 70000
    assert res.claim_results[1].paid_amount == 0
    assert res.claim_results[2].paid_amount == 0
    assert res.total_payout == 70000


# Invariant 7: Invalid claims never consume reserve
def test_invariant_7_invalid_claims_never_consume_reserve(policies, standard_allowance):
    invalid_claim = Claim(
        "tx_bad",
        "alw_inv",
        "p_1",
        "payer_1",
        "m_1",
        50000,
        1,
        1001,
        payer_signature_valid=False,  # Invalid crypto
    )
    for policy in policies:
        res = policy.settle(standard_allowance, [invalid_claim])
        assert res.total_payout == 0
        assert res.claim_results[0].paid_amount == 0
        assert res.claim_results[0].status == SettlementStatus.REJECTED
        assert res.remaining_reserve == standard_allowance.total_reserve


# Invariant 8: Exact UUID replays never produce duplicate payouts
def test_invariant_8_exact_uuid_replays_never_duplicate(policies, standard_allowance):
    c1 = Claim("tx_dup", "alw_inv", "p_1", "payer_1", "m_1", 20000, 1, 1001)
    c1_replay = Claim("tx_dup", "alw_inv", "p_1", "payer_1", "m_1", 20000, 2, 1005)

    for policy in policies:
        res = policy.settle(standard_allowance, [c1, c1_replay])
        assert res.claim_results[0].paid_amount == 20000
        assert res.claim_results[1].paid_amount == 0
        assert res.claim_results[1].status == SettlementStatus.REJECTED
        assert res.total_payout == 20000


# Invariant 9: Conflicting UUID payloads are rejected
def test_invariant_9_conflicting_uuid_payloads_rejected(policies, standard_allowance):
    c1 = Claim("tx_conflict", "alw_inv", "p_1", "payer_1", "m_1", 20000, 1, 1001)
    c1_conflict = Claim("tx_conflict", "alw_inv", "p_1", "payer_1", "m_different", 20000, 2, 1005)

    for policy in policies:
        res = policy.settle(standard_allowance, [c1, c1_conflict])
        assert res.claim_results[0].paid_amount == 20000
        assert res.claim_results[1].paid_amount == 0
        assert res.claim_results[1].status == SettlementStatus.REJECTED
        assert "conflicting" in res.claim_results[1].rejection_reason.lower()


# Invariant 10: No funding source is overdrawn
def test_invariant_10_no_funding_source_overdrawn(policies, standard_allowance):
    # S = C(60000) + H(30000) + F(10000) = 100000
    claims = [
        Claim(f"tx_{i}", "alw_inv", "p_1", "payer_1", f"m_{i}", 40000, i, 1000 + i)
        for i in range(1, 4)
    ]
    for policy in policies:
        res = policy.settle(standard_allowance, claims)
        assert res.total_funded_c <= standard_allowance.allowance_amount
        assert res.total_funded_h <= standard_allowance.payer_hold
        assert res.total_funded_f <= standard_allowance.issuer_guarantee
        assert res.total_funded_c + res.total_funded_h + res.total_funded_f == res.total_payout


# Invariant 11: An honest payer with unique permits and total valid claims within C receives full settlement
def test_invariant_11_honest_payer_within_c_receives_full_settlement(policies, standard_allowance):
    # C = 60000. Honest claims = 20000 + 30000 = 50000 <= C
    c1 = Claim("tx_h1", "alw_inv", "p_1", "payer_1", "m_1", 20000, 1, 1001)
    c2 = Claim("tx_h2", "alw_inv", "p_2", "payer_1", "m_2", 30000, 2, 1002)

    for policy in policies:
        res = policy.settle(standard_allowance, [c1, c2])
        assert res.total_payout == 50000
        assert res.claim_results[0].paid_amount == 20000
        assert res.claim_results[1].paid_amount == 30000
        assert res.total_funded_c == 50000
        assert res.total_funded_h == 0
        assert res.total_funded_f == 0


# Invariant 12: All monetary calculations remain integer paise
def test_invariant_12_all_calculations_remain_integer_paise(policies, standard_allowance):
    c1 = Claim("tx_1", "alw_inv", "p_1", "payer_1", "m_1", 33333, 1, 1001)
    c2 = Claim("tx_2", "alw_inv", "p_2", "payer_1", "m_2", 33333, 2, 1002)
    c3 = Claim("tx_3", "alw_inv", "p_3", "payer_1", "m_3", 33334, 3, 1003)

    for policy in policies:
        res = policy.settle(standard_allowance, [c1, c2, c3])
        assert isinstance(res.total_payout, int)
        assert isinstance(res.total_funded_c, int)
        assert isinstance(res.total_funded_h, int)
        assert isinstance(res.total_funded_f, int)
        assert isinstance(res.remaining_reserve, int)
        for cr in res.claim_results:
            assert isinstance(cr.paid_amount, int)
            assert isinstance(cr.funded_from_c, int)
            assert isinstance(cr.funded_from_h, int)
            assert isinstance(cr.funded_from_f, int)
