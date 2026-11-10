"""Unit tests for attack scenario generators and adversary payoff calculations."""

import pytest
from offline_payment.config import ClaimType
from offline_payment.models.allowance import Allowance
from offline_payment.models.permit import Permit
from offline_payment.settlement.first_claim import FirstClaimSettlement
from offline_payment.settlement.pro_rata import GlobalProRataSettlement
from offline_payment.settlement.payer_liability import PayerLiabilitySettlement
from offline_payment.attacks.double_spend import generate_double_spend_scenario
from offline_payment.attacks.self_claim import generate_self_claim_scenario
from offline_payment.attacks.mule_account import generate_mule_scenario
from offline_payment.attacks.cloned_key import generate_cloned_key_scenario
from offline_payment.attacks.claim_ordering import permute_claim_ordering
from offline_payment.metrics.attacker_profit import calculate_attacker_profit
from offline_payment.metrics.recovery import calculate_recovery_metrics
from offline_payment.metrics.financial_loss import calculate_financial_loss


@pytest.fixture
def test_setup():
    p = Permit("p_1", "alw_att", "payer_1", "pk_1", 50000, 1000, "sig_1")
    allowance = Allowance(
        allowance_id="alw_att",
        payer_id="payer_1",
        allowance_amount=50000,
        payer_hold=50000,
        issuer_guarantee=0,
        settlement_deadline=1000,
        permits=[p],
    )
    return allowance, p


def test_double_spend_generator_and_metrics(test_setup):
    allowance, p = test_setup
    claims = generate_double_spend_scenario(allowance, p, num_merchants=3, claim_amount=50000, mule_first=True)
    assert len(claims) == 3
    assert claims[0].claim_type == ClaimType.MULE
    assert claims[1].claim_type == ClaimType.HONEST_MERCHANT
    assert claims[2].claim_type == ClaimType.HONEST_MERCHANT

    fc = FirstClaimSettlement()
    res_fc = fc.settle(allowance, claims)
    metrics_fc = calculate_recovery_metrics(res_fc)
    profit_fc = calculate_attacker_profit(res_fc, attack_costs=0, payer_is_attacker=True)

    # In FC: Mule gets 50000, Merchants get 0
    assert metrics_fc.mule_payout == 50000
    assert metrics_fc.honest_payout == 0
    assert profit_fc.goods_acquired == 100000  # 2 honest merchant offline claims
    assert profit_fc.recoverable_mule_credit == 50000
    assert profit_fc.payer_owned_debit == 50000
    # Net profit = 100000 + 50000 - 50000 = 100000
    assert profit_fc.net_profit == 100000


def test_mule_scenario_positioning(test_setup):
    allowance, p = test_setup
    permits = [p]

    claims_first = generate_mule_scenario(allowance, permits, total_receivers=4, mule_share_pct=50, mule_position="first")
    assert [c.claim_type == ClaimType.MULE for c in claims_first] == [True, True, False, False]

    claims_last = generate_mule_scenario(allowance, permits, total_receivers=4, mule_share_pct=50, mule_position="last")
    assert [c.claim_type == ClaimType.MULE for c in claims_last] == [False, False, True, True]


def test_cloned_key_victim_loss(test_setup):
    allowance, p = test_setup
    claims = generate_cloned_key_scenario(allowance, [p], num_claims=3, claim_amount=50000, include_mule_drain=True)
    pl = PayerLiabilitySettlement()
    res_pl = pl.settle(allowance, claims)

    # With cloned key, the payer is a victim, not the attacker
    profit = calculate_attacker_profit(res_pl, payer_is_attacker=False)
    loss = calculate_financial_loss(res_pl)

    assert profit.payer_owned_debit == 0  # Attacker suffered no debit!
    assert loss.payer_settled_debit == 100000  # Victim lost ₹1,000


def test_claim_reordering(test_setup):
    allowance, p = test_setup
    claims = generate_double_spend_scenario(allowance, p, num_merchants=3, mule_first=True)
    reordered = permute_claim_ordering(claims, strategy="mule_last")

    assert reordered[0].claim_type == ClaimType.HONEST_MERCHANT
    assert reordered[1].claim_type == ClaimType.HONEST_MERCHANT
    assert reordered[2].claim_type == ClaimType.MULE
    assert [c.ingestion_sequence for c in reordered] == [1, 2, 3]
