"""Correctness and invariant tests for adversarial settlement-policy evaluation.

Verifies:
1. Identical input scenarios are evaluated across all three policies (FC, PR, PL).
2. Global PR allocations sum strictly to min(total_eligible, available_reserve).
3. Global PR invariance to claim ordering (modulo integer remainder tie-breaking).
4. PL never pays a later claim after the first unfundable claim (strict prefix).
5. PL never partially pays an individual claim (full-or-zero payout).
6. FC never accepts more than one valid claim per permit (double-spend rejection).
7. Funding-source attribution never exceeds C, H, or F limits.
8. Total payout never exceeds total available reserve S = C + H + F.
9. Attacker payout includes only explicitly classified attacker-controlled accounts.
10. Attacker profit is mathematically non-double-counted.
11. Zero-denominator metrics return None (not fabricated values).
12. Invariance of baseline outputs across existing and new frameworks.
13. Attacker-profit explicit component audit (goods acquired, mule proceeds, payer debit, frozen funds).
14. Common-eligibility vs shared-permit eligibility semantics.
15. Exact analytical reconciliation of Small Mule [200, 650, 650] in PL.
16. Account-splitting invariance under Global Pro-Rata.
17. Attacker payout is strictly decoupled from attacker profit.
"""

import itertools
import pytest

from offline_payment.config import ClaimType, SettlementPolicy, SettlementStatus
from offline_payment.metrics.adversarial_metrics import calculate_adversarial_metrics
from offline_payment.metrics.attacker_profit import calculate_attacker_profit
from offline_payment.models.allowance import Allowance
from offline_payment.models.claim import Claim
from offline_payment.models.permit import Permit
from offline_payment.settlement.first_claim import FirstClaimSettlement
from offline_payment.settlement.payer_liability import PayerLiabilitySettlement
from offline_payment.settlement.pro_rata import GlobalProRataSettlement
from offline_payment.simulation.scenario_generator import (
    AdversarialScenario,
    AdversarialScenarioGenerator,
)


@pytest.fixture
def generator() -> AdversarialScenarioGenerator:
    return AdversarialScenarioGenerator()


@pytest.fixture
def standard_allowance() -> Allowance:
    p1 = Permit("p_1", "alw_adv", "payer_1", "pk_1", 50000, 1000, "sig_1")
    p2 = Permit("p_2", "alw_adv", "payer_1", "pk_1", 50000, 1000, "sig_2")
    p3 = Permit("p_3", "alw_adv", "payer_1", "pk_1", 50000, 1000, "sig_3")
    return Allowance(
        allowance_id="alw_adv",
        payer_id="payer_1",
        allowance_amount=50000,
        payer_hold=50000,
        issuer_guarantee=0,
        settlement_deadline=1000,
        permits=[p1, p2, p3],
    )


@pytest.fixture
def policies() -> list:
    return [
        FirstClaimSettlement(),
        GlobalProRataSettlement(),
        PayerLiabilitySettlement(),
    ]


# -----------------------------------------------------------------------------
# Test 1: Identical input scenarios passed to all three policies
# -----------------------------------------------------------------------------
def test_identical_input_scenarios_passed_to_all_policies(generator, policies):
    scenario = generator.generate_scenario(
        scenario_id="test_identical",
        total_eligible_claim_value=150000,
        num_honest_merchants=2,
        num_attacker_payees=1,
        mule_claim_share=0.3333333333333333,
        claim_amounts=[50000, 50000, 50000],
        permit_conflict="distinct_permits",
        available_c=50000,
        available_h=50000,
        available_f=0,
    )

    results = {}
    for pol in policies:
        res = pol.settle(scenario.allowance, scenario.claims)
        results[pol.policy_type.name] = res
        assert len(res.claim_results) == 3
        for idx, cr in enumerate(res.claim_results):
            assert cr.claim.amount == scenario.claims[idx].amount
            assert cr.claim.permit_id == scenario.claims[idx].permit_id
            assert cr.claim.payee_id == scenario.claims[idx].payee_id


# -----------------------------------------------------------------------------
# Test 2: Global PR allocations sum to min(total_eligible, available_reserve)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("reserve,claims_total", [
    (100000, 150000),
    (150000, 150000),
    (200000, 150000),
    (37500, 150000),
    (0, 150000),
])
def test_global_pr_allocation_sums_to_distributable_reserve(generator, reserve, claims_total):
    pr = GlobalProRataSettlement()
    c = min(reserve, 50000)
    h = min(reserve - c, 50000)
    f = reserve - c - h

    scenario = generator.generate_scenario(
        scenario_id=f"pr_sum_test_{reserve}",
        total_eligible_claim_value=claims_total,
        num_honest_merchants=2,
        num_attacker_payees=1,
        claim_amounts=[claims_total // 3] * 3,
        available_c=c,
        available_h=h,
        available_f=f,
    )

    res = pr.settle(scenario.allowance, scenario.claims)
    expected_payout = min(claims_total, reserve)
    assert res.total_payout == expected_payout
    assert sum(cr.paid_amount for cr in res.claim_results) == expected_payout
    for cr in res.claim_results:
        assert 0 <= cr.paid_amount <= cr.requested_amount


# -----------------------------------------------------------------------------
# Test 3: Global PR order invariance (modulo integer remainder tie-breaking)
# -----------------------------------------------------------------------------
def test_global_pr_order_invariance_modulo_remainder_ties(generator):
    pr = GlobalProRataSettlement()
    base_scenario = generator.generate_scenario(
        scenario_id="pr_invariance_test",
        total_eligible_claim_value=150000,
        num_honest_merchants=2,
        num_attacker_payees=1,
        claim_amounts=[50000, 50000, 50000],
        available_c=50000,
        available_h=50000,
        available_f=0,
    )

    all_perms = list(itertools.permutations([0, 1, 2]))
    for perm in all_perms:
        reordered = base_scenario.clone_with_order(list(perm))
        res = pr.settle(reordered.allowance, reordered.claims)

        assert res.total_payout == 100000
        for cr in res.claim_results:
            assert cr.paid_amount in (33333, 33334)


# -----------------------------------------------------------------------------
# Test 4: PL strict prefix (never pays later claim after unfundable claim)
# -----------------------------------------------------------------------------
def test_pl_strict_prefix_halts_after_first_unfundable_claim(generator):
    pl = PayerLiabilitySettlement()
    scenario = generator.generate_scenario(
        scenario_id="pl_strict_prefix_halt",
        total_eligible_claim_value=110000,
        num_honest_merchants=2,
        num_attacker_payees=1,
        claim_amounts=[50000, 50000, 10000],
        available_c=50000,
        available_h=20000,
        available_f=0,
    )

    res = pl.settle(scenario.allowance, scenario.claims)
    assert res.claim_results[0].paid_amount == 50000
    assert res.claim_results[0].status == SettlementStatus.SETTLED_FULL

    assert res.claim_results[1].paid_amount == 0
    assert res.claim_results[1].status == SettlementStatus.UNPAID

    # Claim 3 remains unpaid even though remaining reserve >= 10,000
    assert res.claim_results[2].paid_amount == 0
    assert res.claim_results[2].status == SettlementStatus.UNPAID
    assert res.remaining_reserve == 20000


# -----------------------------------------------------------------------------
# Test 5: PL never partially pays an individual claim
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("amounts,reserve", [
    ([50000, 50000, 50000], 75000),
    ([20000, 65000, 65000], 80000),
    ([80000, 35000, 35000], 100000),
])
def test_pl_never_partially_pays_claims(generator, amounts, reserve):
    pl = PayerLiabilitySettlement()
    scenario = generator.generate_scenario(
        scenario_id="pl_no_partial",
        total_eligible_claim_value=sum(amounts),
        num_honest_merchants=2,
        num_attacker_payees=1,
        claim_amounts=amounts,
        available_c=reserve,
        available_h=0,
        available_f=0,
    )

    res = pl.settle(scenario.allowance, scenario.claims)
    for cr in res.claim_results:
        assert cr.paid_amount in (0, cr.requested_amount)
        if cr.paid_amount == 0:
            assert cr.status in (SettlementStatus.UNPAID, SettlementStatus.REJECTED)
        else:
            assert cr.status == SettlementStatus.SETTLED_FULL


# -----------------------------------------------------------------------------
# Test 6: FC never accepts more than one valid claim per permit
# -----------------------------------------------------------------------------
def test_fc_rejects_subsequent_claims_referencing_same_permit(generator):
    fc = FirstClaimSettlement()
    scenario = generator.generate_scenario(
        scenario_id="fc_double_spend_permit",
        total_eligible_claim_value=150000,
        num_honest_merchants=2,
        num_attacker_payees=1,
        claim_amounts=[50000, 50000, 50000],
        permit_conflict="same_permit",
        available_c=100000,
        available_h=50000,
        available_f=0,
    )

    res = fc.settle(scenario.allowance, scenario.claims)
    assert res.claim_results[0].status == SettlementStatus.SETTLED_FULL
    assert res.claim_results[0].paid_amount == 50000

    for cr in res.claim_results[1:]:
        assert cr.status == SettlementStatus.REJECTED
        assert cr.paid_amount == 0
        assert "double-spend" in str(cr.rejection_reason).lower()


# -----------------------------------------------------------------------------
# Test 7: Funding-source attribution never exceeds C, H, or F
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("c,h,f", [
    (30000, 40000, 20000),
    (50000, 50000, 0),
    (0, 0, 50000),
    (100000, 0, 0),
])
def test_funding_tier_bounds_respected(generator, policies, c, h, f):
    scenario = generator.generate_scenario(
        scenario_id="funding_tiers_test",
        total_eligible_claim_value=150000,
        num_honest_merchants=2,
        num_attacker_payees=1,
        claim_amounts=[50000, 50000, 50000],
        available_c=c,
        available_h=h,
        available_f=f,
    )

    for pol in policies:
        res = pol.settle(scenario.allowance, scenario.claims)
        assert res.total_funded_c <= c
        assert res.total_funded_h <= h
        assert res.total_funded_f <= f
        assert res.total_funded_c + res.total_funded_h + res.total_funded_f == res.total_payout


# -----------------------------------------------------------------------------
# Test 8: Total payout never exceeds total available reserve S = C + H + F
# -----------------------------------------------------------------------------
def test_total_payout_never_exceeds_reserve(generator, policies):
    for s_val in [10000, 50000, 99999, 150000, 200000]:
        c = min(s_val, 50000)
        h = s_val - c
        scenario = generator.generate_scenario(
            scenario_id=f"reserve_ceiling_{s_val}",
            total_eligible_claim_value=150000,
            num_honest_merchants=2,
            num_attacker_payees=1,
            claim_amounts=[50000, 50000, 50000],
            available_c=c,
            available_h=h,
            available_f=0,
        )
        for pol in policies:
            res = pol.settle(scenario.allowance, scenario.claims)
            assert res.total_payout <= s_val
            assert res.total_payout + res.remaining_reserve == s_val


# -----------------------------------------------------------------------------
# Test 9: Attacker payout includes only explicitly classified attacker accounts
# -----------------------------------------------------------------------------
def test_attacker_payout_explicit_classification(generator, policies):
    scenario = generator.generate_scenario(
        scenario_id="attacker_classification",
        total_eligible_claim_value=150000,
        num_honest_merchants=2,
        num_attacker_payees=1,
        claim_amounts=[50000, 50000, 50000],
        available_c=50000,
        available_h=50000,
        available_f=0,
    )

    assert scenario.claims[0].attacker_controls_payee is True
    assert scenario.claims[1].attacker_controls_payee is False
    assert scenario.claims[2].attacker_controls_payee is False

    for pol in policies:
        res = pol.settle(scenario.allowance, scenario.claims)
        metrics = calculate_adversarial_metrics(res, scenario_id=scenario.scenario_id)

        assert metrics.attacker_payout == res.claim_results[0].paid_amount
        assert metrics.honest_payout == res.claim_results[1].paid_amount + res.claim_results[2].paid_amount
        assert metrics.attacker_payout + metrics.honest_payout == res.total_payout


# -----------------------------------------------------------------------------
# Test 10: Attacker profit is mathematically non-double-counted
# -----------------------------------------------------------------------------
def test_attacker_profit_accounting_invariance(generator, policies):
    scenario = generator.generate_scenario(
        scenario_id="profit_formula_test",
        total_eligible_claim_value=150000,
        num_honest_merchants=2,
        num_attacker_payees=1,
        claim_amounts=[50000, 50000, 50000],
        available_c=50000,
        available_h=50000,
        available_f=0,
        attack_costs_paise=5000,
    )

    for pol in policies:
        res = pol.settle(scenario.allowance, scenario.claims)
        metrics = calculate_adversarial_metrics(
            res,
            scenario_id=scenario.scenario_id,
            attack_costs_paise=5000,
            payer_is_attacker=True,
        )

        expected_profit = (
            (metrics.goods_value_acquired + metrics.recoverable_mule_proceeds)
            - (metrics.payer_owned_debit + metrics.actual_attacker_costs)
        )
        assert metrics.net_economic_profit == expected_profit


# -----------------------------------------------------------------------------
# Test 11: Zero-denominator metrics return None
# -----------------------------------------------------------------------------
def test_zero_denominator_metrics_handled_gracefully(generator):
    pr = GlobalProRataSettlement()

    scenario_no_honest = generator.generate_scenario(
        scenario_id="no_honest",
        total_eligible_claim_value=50000,
        num_honest_merchants=0,
        num_attacker_payees=1,
        mule_claim_share=1.0,
        claim_amounts=[50000],
        available_c=50000,
        available_h=0,
        available_f=0,
    )
    res1 = pr.settle(scenario_no_honest.allowance, scenario_no_honest.claims)
    m1 = calculate_adversarial_metrics(res1)
    assert m1.honest_eligible == 0
    assert m1.honest_recovery_rate is None

    scenario_zero_reserve = generator.generate_scenario(
        scenario_id="zero_reserve",
        total_eligible_claim_value=50000,
        num_honest_merchants=1,
        num_attacker_payees=0,
        mule_claim_share=0.0,
        claim_amounts=[50000],
        available_c=0,
        available_h=0,
        available_f=0,
    )
    res2 = pr.settle(scenario_zero_reserve.allowance, scenario_zero_reserve.claims)
    m2 = calculate_adversarial_metrics(res2)
    assert m2.available_reserve == 0
    assert m2.total_payout == 0
    assert m2.reserve_utilization is None
    assert m2.mule_advantage is None


# -----------------------------------------------------------------------------
# Test 12: Baseline outputs remain identical
# -----------------------------------------------------------------------------
def test_baseline_outputs_remain_strictly_identical():
    from offline_payment.experiments.policy_comparison import run_initial_experiment

    outcomes = run_initial_experiment()
    assert outcomes["FC"].mule_payout_paise == 50000
    assert outcomes["FC"].merchant_a_payout_paise == 0
    assert outcomes["FC"].merchant_b_payout_paise == 0
    assert outcomes["FC"].total_payout_paise == 50000
    assert outcomes["FC"].honest_recovery_rate == 0.0

    assert outcomes["PR"].mule_payout_paise == 33334
    assert outcomes["PR"].total_payout_paise == 100000
    assert round(outcomes["PR"].honest_recovery_rate, 3) == 0.667

    assert outcomes["PL"].mule_payout_paise == 50000
    assert outcomes["PL"].merchant_a_payout_paise == 50000
    assert outcomes["PL"].merchant_b_payout_paise == 0
    assert outcomes["PL"].total_payout_paise == 100000
    assert outcomes["PL"].honest_recovery_rate == 0.50


# -----------------------------------------------------------------------------
# Test 13: Attacker-Profit Explicit Component Audit (Task 1)
# -----------------------------------------------------------------------------
def test_attacker_profit_explicit_components_and_no_double_counting(generator):
    scenario = generator.generate_scenario(
        scenario_id="audit_profit_components",
        total_eligible_claim_value=150000,
        num_honest_merchants=2,
        num_attacker_payees=1,
        claim_amounts=[50000, 50000, 50000],
        available_c=50000,
        available_h=50000,
        available_f=0,
    )

    pl = PayerLiabilitySettlement()
    res = pl.settle(scenario.allowance, scenario.claims)

    # Assume 10,000 paise in operational attack costs and 5,000 paise in frozen funds
    payoff = calculate_attacker_profit(
        res,
        attack_costs=10000,
        frozen_funds=5000,
        payer_is_attacker=True,
    )

    # 1. Goods acquired = 2 honest claims * 50,000 = 100,000
    assert payoff.goods_value_acquired == 100000
    # 2. Mule payout = 50,000
    assert payoff.mule_account_payout == 50000
    # 3. Frozen funds = 5,000
    assert payoff.frozen_or_reversed_funds == 5000
    # 4. Recoverable mule proceeds = 50,000 - 5,000 = 45,000
    assert payoff.recoverable_mule_proceeds == 45000
    # 5. Payer debit = total payer funded (C+H = 100,000)
    assert payoff.payer_owned_debit == 100000
    # 6. Actual attack costs = 10,000
    assert payoff.actual_attacker_costs == 10000
    # 7. Net Economic Profit = (100,000 + 45,000) - (100,000 + 10,000) = 35,000
    assert payoff.net_economic_profit == 35000

    # Ensure payout is NOT equated with profit:
    assert payoff.mule_account_payout != payoff.net_economic_profit


# -----------------------------------------------------------------------------
# Test 14: Common-Eligibility vs Shared-Permit Semantics (Tasks 2 & 3)
# -----------------------------------------------------------------------------
def test_common_eligibility_vs_shared_permit_semantics(generator):
    fc = FirstClaimSettlement()

    # Common Eligibility: 3 distinct permits
    scen_distinct = generator.generate_scenario(
        scenario_id="distinct_eligibility",
        total_eligible_claim_value=150000,
        num_honest_merchants=2,
        num_attacker_payees=1,
        claim_amounts=[50000, 50000, 50000],
        permit_conflict="distinct_permits",
        available_c=50000,
        available_h=50000,
        available_f=0,
    )
    res_distinct = fc.settle(scen_distinct.allowance, scen_distinct.claims)
    # Under distinct permits, all 3 are eligible for consideration
    assert res_distinct.total_eligible_count == 3
    assert res_distinct.total_payout == 100000
    # 3rd claim is UNPAID due to reserve limit, NOT rejected as double spend!
    assert res_distinct.claim_results[2].status == SettlementStatus.UNPAID

    # Shared Permit: 1 shared permit (double-spending conflict)
    scen_shared = generator.generate_scenario(
        scenario_id="shared_eligibility",
        total_eligible_claim_value=150000,
        num_honest_merchants=2,
        num_attacker_payees=1,
        claim_amounts=[50000, 50000, 50000],
        permit_conflict="same_permit",
        available_c=50000,
        available_h=50000,
        available_f=0,
    )
    res_shared = fc.settle(scen_shared.allowance, scen_shared.claims)
    # Under shared permit, only 1 claim is accepted; 2 are REJECTED
    assert sum(1 for cr in res_shared.claim_results if cr.status == SettlementStatus.REJECTED) == 2
    assert res_shared.total_payout == 50000
    assert res_shared.remaining_reserve == 50000  # Stranded


# -----------------------------------------------------------------------------
# Test 15: Exact Analytical Small Mule Reconciliation in PL (Task 4)
# -----------------------------------------------------------------------------
def test_small_mule_analytical_reconciliation_exact(generator):
    pl = PayerLiabilitySettlement()
    scenario = generator.generate_scenario(
        scenario_id="small_mule_analytical",
        total_eligible_claim_value=150000,
        num_honest_merchants=2,
        num_attacker_payees=1,
        claim_amounts=[20000, 65000, 65000],
        permit_conflict="distinct_permits",
        available_c=50000,
        available_h=50000,
        available_f=0,
    )

    perms = list(itertools.permutations([0, 1, 2]))
    assert len(perms) == 6

    payouts = []
    stranded_reserves = []
    attacker_profits = []

    for p in perms:
        reordered = scenario.clone_with_order(list(p))
        res = pl.settle(reordered.allowance, reordered.claims)
        metrics = calculate_adversarial_metrics(res, payer_is_attacker=True)

        payouts.append(metrics.total_payout)
        stranded_reserves.append(metrics.stranded_reserve)
        attacker_profits.append(metrics.net_economic_profit)

    # 4 permutations must have payout 85,000 and stranded 15,000
    assert payouts.count(85000) == 4
    assert stranded_reserves.count(15000) == 4

    # 2 permutations must have payout 65,000 and stranded 35,000
    assert payouts.count(65000) == 2
    assert stranded_reserves.count(35000) == 2

    # Exact expected values:
    mean_stranded = sum(stranded_reserves) / 6.0
    mean_payout = sum(payouts) / 6.0
    mean_utilization = mean_payout / 100000.0

    assert round(mean_stranded, 2) == 21666.67  # Exactly 216.67 INR
    assert round(mean_payout, 2) == 78333.33    # Exactly 783.33 INR
    assert round(mean_utilization * 100, 2) == 78.33  # Exactly 78.33%

    # Attacker net profit is strictly constant at 65,000 paise (650 INR) across all 6 orders!
    assert all(p == 65000 for p in attacker_profits)


# -----------------------------------------------------------------------------
# Test 16: Account-Splitting Invariance in Global Pro-Rata (Task 5)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("k", [1, 2, 5, 10])
def test_global_pr_account_splitting_invariance(generator, k):
    pr = GlobalProRataSettlement()
    aggregate_mule = 50000
    base_mule_amt = aggregate_mule // k
    rem_mule = aggregate_mule % k
    mule_amounts = [base_mule_amt + (1 if i < rem_mule else 0) for i in range(k)]
    all_amounts = mule_amounts + [50000, 50000]

    scenario = generator.generate_scenario(
        scenario_id=f"pr_acct_split_k{k}",
        total_eligible_claim_value=150000,
        num_honest_merchants=2,
        num_attacker_payees=k,
        claim_amounts=all_amounts,
        permit_conflict="distinct_permits",
        available_c=50000,
        available_h=50000,
        available_f=0,
    )

    res = pr.settle(scenario.allowance, scenario.claims)
    metrics = calculate_adversarial_metrics(res)

    # In Global PR, aggregate mule payout must remain within +- 1 paise of 33,333 paise
    assert abs(metrics.attacker_payout - 33333.33) <= 1.0
    # Honest recovery rate must be exactly 66.67%
    assert round(metrics.honest_recovery_rate, 3) == 0.667
    # Total payout must be exactly 100,000
    assert res.total_payout == 100000


# -----------------------------------------------------------------------------
# Test 17: POS Goods Release Accounting Independent Verification
# -----------------------------------------------------------------------------
def test_pos_goods_release_accounting_independent_cases(standard_allowance):
    """Test all independent cases of POS goods release accounting."""
    pl = PayerLiabilitySettlement()

    # Case 1: Goods released = False, all other fields valid
    c_no_goods = Claim(
        tx_uuid="tx_no_goods",
        allowance_id="alw_adv",
        permit_id="p_1",
        payer_id="payer_1",
        payee_id="m_1",
        amount=50000,
        ingestion_sequence=1,
        submission_time=1001,
        offline_accepted=True,
        pos_validation_passed=True,
        goods_released=False,  # Physical goods NOT surrendered!
        claim_type=ClaimType.HONEST_MERCHANT,
    )
    res1 = pl.settle(standard_allowance, [c_no_goods])
    payoff1 = calculate_attacker_profit(res1, payer_is_attacker=True)
    assert payoff1.goods_value_acquired == 0, "Goods released=False must yield 0 goods acquired"

    # Case 2: POS validation = False, goods released = True
    c_no_pos = Claim(
        tx_uuid="tx_no_pos",
        allowance_id="alw_adv",
        permit_id="p_1",
        payer_id="payer_1",
        payee_id="m_1",
        amount=50000,
        ingestion_sequence=1,
        submission_time=1001,
        offline_accepted=True,
        pos_validation_passed=False,  # Failed terminal check!
        goods_released=True,
        claim_type=ClaimType.HONEST_MERCHANT,
    )
    res2 = pl.settle(standard_allowance, [c_no_pos])
    payoff2 = calculate_attacker_profit(res2, payer_is_attacker=True)
    assert payoff2.goods_value_acquired == 0, "POS validation=False must yield 0 goods acquired"

    # Case 3: Offline acceptance = False
    c_no_accept = Claim(
        tx_uuid="tx_no_accept",
        allowance_id="alw_adv",
        permit_id="p_1",
        payer_id="payer_1",
        payee_id="m_1",
        amount=50000,
        ingestion_sequence=1,
        submission_time=1001,
        offline_accepted=False,  # Rejected offline!
        pos_validation_passed=True,
        goods_released=True,
        claim_type=ClaimType.HONEST_MERCHANT,
    )
    res3 = pl.settle(standard_allowance, [c_no_accept])
    payoff3 = calculate_attacker_profit(res3, payer_is_attacker=True)
    assert payoff3.goods_value_acquired == 0, "Offline accepted=False must yield 0 goods acquired"

    # Case 4: Invalid cryptographic signature
    c_bad_sig = Claim(
        tx_uuid="tx_bad_sig",
        allowance_id="alw_adv",
        permit_id="p_1",
        payer_id="payer_1",
        payee_id="m_1",
        amount=50000,
        ingestion_sequence=1,
        submission_time=1001,
        offline_accepted=True,
        pos_validation_passed=True,
        goods_released=True,
        payer_signature_valid=False,  # Bad signature!
        claim_type=ClaimType.HONEST_MERCHANT,
    )
    res4 = pl.settle(standard_allowance, [c_bad_sig])
    payoff4 = calculate_attacker_profit(res4, payer_is_attacker=True)
    assert payoff4.goods_value_acquired == 0, "Invalid signature must yield 0 goods acquired"

    # Case 5: Valid honest merchant claim with goods released
    c_valid_honest = Claim(
        tx_uuid="tx_valid_honest",
        allowance_id="alw_adv",
        permit_id="p_1",
        payer_id="payer_1",
        payee_id="m_1",
        amount=50000,
        ingestion_sequence=1,
        submission_time=1001,
        offline_accepted=True,
        pos_validation_passed=True,
        goods_released=True,
        claim_type=ClaimType.HONEST_MERCHANT,
    )
    res5 = pl.settle(standard_allowance, [c_valid_honest])
    payoff5 = calculate_attacker_profit(res5, payer_is_attacker=True)
    assert payoff5.goods_value_acquired == 50000, "Fully qualified honest claim must yield face value"

    # Case 6: Mule self-transfer
    c_mule = Claim(
        tx_uuid="tx_mule",
        allowance_id="alw_adv",
        permit_id="p_1",
        payer_id="payer_1",
        payee_id="mule_1",
        amount=50000,
        ingestion_sequence=1,
        submission_time=1001,
        offline_accepted=True,
        pos_validation_passed=True,
        goods_released=True,
        claim_type=ClaimType.MULE,
        attacker_controls_payee=True,
    )
    res6 = pl.settle(standard_allowance, [c_mule])
    payoff6 = calculate_attacker_profit(res6, payer_is_attacker=True)
    assert payoff6.goods_value_acquired == 0, "Mule claim must NEVER count as goods acquired"
    assert payoff6.mule_account_payout == 50000, "Mule claim payout must be credited to mule_account_payout"


# -----------------------------------------------------------------------------
# Test 18: Frozen Funds (0%, 50%, 100%) and Bounds Validation
# -----------------------------------------------------------------------------
def test_frozen_funds_percentages_and_bounds_validation(standard_allowance):
    """Test 0%, 50%, 100% frozen funds and out-of-bounds error handling."""
    pl = PayerLiabilitySettlement()
    c_mule = Claim(
        tx_uuid="tx_mule_freeze",
        allowance_id="alw_adv",
        permit_id="p_1",
        payer_id="payer_1",
        payee_id="mule_1",
        amount=50000,
        ingestion_sequence=1,
        submission_time=1001,
        claim_type=ClaimType.MULE,
        attacker_controls_payee=True,
    )
    res = pl.settle(standard_allowance, [c_mule])
    assert res.total_payout == 50000

    # 0% frozen funds
    payoff_0 = calculate_attacker_profit(res, frozen_funds=0, payer_is_attacker=True)
    assert payoff_0.mule_account_payout == 50000
    assert payoff_0.frozen_or_reversed_funds == 0
    assert payoff_0.recoverable_mule_proceeds == 50000

    # 50% frozen funds
    payoff_50 = calculate_attacker_profit(res, frozen_funds=25000, payer_is_attacker=True)
    assert payoff_50.mule_account_payout == 50000
    assert payoff_50.frozen_or_reversed_funds == 25000
    assert payoff_50.recoverable_mule_proceeds == 25000

    # 100% frozen funds
    payoff_100 = calculate_attacker_profit(res, frozen_funds=50000, payer_is_attacker=True)
    assert payoff_100.mule_account_payout == 50000
    assert payoff_100.frozen_or_reversed_funds == 50000
    assert payoff_100.recoverable_mule_proceeds == 0

    # Negative frozen funds must raise ValueError
    with pytest.raises(ValueError, match="non-negative integer"):
        calculate_attacker_profit(res, frozen_funds=-1)

    # Negative attack costs must raise ValueError
    with pytest.raises(ValueError, match="non-negative integer"):
        calculate_attacker_profit(res, attack_costs=-500)

    # Frozen funds exceeding mule payout must raise ValueError
    with pytest.raises(ValueError, match="cannot exceed total mule"):
        calculate_attacker_profit(res, frozen_funds=50001)


# -----------------------------------------------------------------------------
# Test 19: Malicious Payer vs. Compromised Victim Liability
# -----------------------------------------------------------------------------
def test_malicious_payer_vs_compromised_victim_liability(standard_allowance):
    """Test difference in attacker profit between malicious payer and compromised victim."""
    pl = PayerLiabilitySettlement()
    c_honest = Claim(
        tx_uuid="tx_honest_h1",
        allowance_id="alw_adv",
        permit_id="p_1",
        payer_id="payer_1",
        payee_id="merchant_1",
        amount=50000,
        ingestion_sequence=1,
        submission_time=1001,
        claim_type=ClaimType.HONEST_MERCHANT,
    )
    c_mule = Claim(
        tx_uuid="tx_mule_m1",
        allowance_id="alw_adv",
        permit_id="p_2",
        payer_id="payer_1",
        payee_id="mule_1",
        amount=50000,
        ingestion_sequence=2,
        submission_time=1002,
        claim_type=ClaimType.MULE,
        attacker_controls_payee=True,
    )

    res = pl.settle(standard_allowance, [c_honest, c_mule])
    assert res.total_payout == 100000
    assert res.total_payer_funded == 100000  # C(50k) + H(50k)

    # 1. Malicious payer (attacker owns the payer collateral):
    # Attacker acquired 50k goods + 50k mule proceeds, but lost 100k payer debit!
    payoff_malicious = calculate_attacker_profit(res, payer_is_attacker=True)
    assert payoff_malicious.goods_value_acquired == 50000
    assert payoff_malicious.recoverable_mule_proceeds == 50000
    assert payoff_malicious.payer_owned_debit == 100000
    assert payoff_malicious.net_economic_profit == 0  # (50k + 50k) - 100k = 0

    # 2. Compromised victim (attacker stole victim's key, payer_is_attacker = False):
    # Victim loses collateral; attacker suffers 0 payer debit!
    payoff_victim = calculate_attacker_profit(res, payer_is_attacker=False)
    assert payoff_victim.goods_value_acquired == 50000
    assert payoff_victim.recoverable_mule_proceeds == 50000
    assert payoff_victim.payer_owned_debit == 0
    assert payoff_victim.net_economic_profit == 100000  # (50k + 50k) - 0 = 100k

    assert payoff_victim.net_economic_profit - payoff_malicious.net_economic_profit == 100000
