"""Regression and defect-prevention tests for the offline payment simulator."""

import pytest
from offline_payment.config import ClaimType, SettlementStatus
from offline_payment.models.allowance import Allowance
from offline_payment.models.permit import Permit
from offline_payment.models.claim import Claim
from offline_payment.settlement.first_claim import FirstClaimSettlement
from offline_payment.settlement.pro_rata import GlobalProRataSettlement
from offline_payment.settlement.payer_liability import PayerLiabilitySettlement
from offline_payment.validation.claim_validator import ClaimValidator
from offline_payment.attacks.mule_account import calculate_mule_count, generate_mule_scenario
from offline_payment.metrics.recovery import calculate_recovery_metrics
from offline_payment.metrics.attacker_profit import calculate_attacker_profit
from offline_payment.experiments.policy_comparison import run_initial_experiment


# Regression 1: Every generated receiver-sweep claim references an existing permit and allowance
def test_receiver_sweep_claims_reference_existing_permit_and_allowance():
    for n_rec in [1, 2, 3, 5, 10, 20]:
        for m_share in [0, 25, 50, 75, 100]:
            allowance_id = f"alw_swp_{n_rec}_{m_share}_first"
            permit_id = f"p_swp_{n_rec}_{m_share}_first"

            permit = Permit(
                permit_id=permit_id,
                allowance_id=allowance_id,
                payer_id="payer_test",
                payer_public_key="pk_test",
                denomination=50000,
                settlement_deadline=1000,
                issuer_signature="sig_root",
            )
            allowance = Allowance(
                allowance_id=allowance_id,
                payer_id="payer_test",
                allowance_amount=50000,
                payer_hold=50000,
                issuer_guarantee=0,
                settlement_deadline=1000,
                permits=[permit],
            )
            claims = generate_mule_scenario(
                allowance=allowance,
                permits=[permit],
                total_receivers=n_rec,
                mule_share_pct=m_share,
                mule_position="first",
                claim_amount=50000,
            )

            assert len(claims) == n_rec
            for c in claims:
                assert c.allowance_id == allowance.allowance_id
                assert c.permit_id == permit.permit_id
                assert permit.allowance_id == allowance.allowance_id


# Regression 2: Generated valid claims are not rejected because of reference mismatches
def test_generated_receiver_sweep_claims_not_rejected_by_reference_mismatch():
    allowance_id = "alw_swp_3_50_first"
    permit_id = "p_swp_3_50_first"

    permit = Permit(
        permit_id=permit_id,
        allowance_id=allowance_id,
        payer_id="payer_test",
        payer_public_key="pk_test",
        denomination=50000,
        settlement_deadline=1000,
        issuer_signature="sig_root",
    )
    allowance = Allowance(
        allowance_id=allowance_id,
        payer_id="payer_test",
        allowance_amount=50000,
        payer_hold=50000,
        issuer_guarantee=0,
        settlement_deadline=1000,
        permits=[permit],
    )
    claims = generate_mule_scenario(
        allowance=allowance,
        permits=[permit],
        total_receivers=3,
        mule_share_pct=50,
        mule_position="first",
        claim_amount=50000,
    )

    validator = ClaimValidator(allowance)
    for c in claims:
        val_res = validator.validate_claim(c)
        assert val_res.is_valid is True, f"Claim {c.tx_uuid} failed validation: {val_res.error_message}"
        assert val_res.error_message is None


# Regression 3: The receiver sweep produces nonzero settlements in configurations where reserve and claims permit
def test_receiver_sweep_produces_nonzero_settlements():
    allowance_id = "alw_swp_3_33_first"
    permit_id = "p_swp_3_33_first"

    permit = Permit(
        permit_id=permit_id,
        allowance_id=allowance_id,
        payer_id="payer_test",
        payer_public_key="pk_test",
        denomination=50000,
        settlement_deadline=1000,
        issuer_signature="sig_root",
    )
    allowance = Allowance(
        allowance_id=allowance_id,
        payer_id="payer_test",
        allowance_amount=50000,
        payer_hold=50000,
        issuer_guarantee=0,
        settlement_deadline=1000,
        permits=[permit],
    )
    claims = generate_mule_scenario(
        allowance=allowance,
        permits=[permit],
        total_receivers=3,
        mule_share_pct=33,
        mule_position="first",
        claim_amount=50000,
    )

    fc = FirstClaimSettlement().settle(allowance, claims)
    pr = GlobalProRataSettlement().settle(allowance, claims)
    pl = PayerLiabilitySettlement().settle(allowance, claims)

    assert fc.total_payout == 50000, "FC should pay first claim (50000)"
    assert pr.total_payout == 100000, "PR should allocate full 100000 reserve"
    assert pl.total_payout == 100000, "PL should pay first two claims in full"

    # Ensure none failed due to reference mismatches
    for r in [fc, pr, pl]:
        for cr in r.claim_results:
            assert cr.validation_passed is True


# Regression 4: Zero eligible claims produce undefined recovery (None), not 100%
def test_zero_eligible_claims_produce_undefined_recovery_not_100_percent():
    permit = Permit("p_0", "alw_0", "payer_0", "pk_0", 50000, 1000, "sig_0")
    allowance = Allowance("alw_0", "payer_0", 50000, 50000, 0, 1000, [permit])

    # Batch with no claims
    res_empty = FirstClaimSettlement().settle(allowance, [])
    metrics_empty = calculate_recovery_metrics(res_empty)
    assert metrics_empty.overall_recovery_rate is None
    assert metrics_empty.honest_recovery_rate is None
    assert metrics_empty.mule_recovery_rate is None

    # Batch with only cryptographically invalid claims
    bad_claim = Claim(
        tx_uuid="tx_bad",
        allowance_id="alw_0",
        permit_id="p_0",
        payer_id="payer_0",
        payee_id="m_1",
        amount=50000,
        ingestion_sequence=1,
        submission_time=1000,
        payer_signature_valid=False,  # Invalid!
        claim_type=ClaimType.HONEST_MERCHANT,
    )
    res_invalid = FirstClaimSettlement().settle(allowance, [bad_claim])
    metrics_invalid = calculate_recovery_metrics(res_invalid)
    assert metrics_invalid.total_eligible == 0
    assert metrics_invalid.overall_recovery_rate is None
    assert metrics_invalid.honest_recovery_rate is None
    assert metrics_invalid.mule_recovery_rate is None


# Regression 5: Structurally invalid claims do not count as goods acquired
def test_structurally_invalid_claims_do_not_count_as_goods_acquired():
    permit = Permit("p_1", "alw_1", "payer_1", "pk_1", 50000, 1000, "sig_1")
    allowance = Allowance("alw_1", "payer_1", 50000, 50000, 0, 1000, [permit])

    # Structurally invalid claim (e.g. invalid signature)
    bad_claim = Claim(
        tx_uuid="tx_bad_sig",
        allowance_id="alw_1",
        permit_id="p_1",
        payer_id="payer_1",
        payee_id="m_1",
        amount=50000,
        ingestion_sequence=1,
        submission_time=1000,
        payer_signature_valid=False,
        claim_type=ClaimType.HONEST_MERCHANT,
        offline_accepted=True,
    )

    res = FirstClaimSettlement().settle(allowance, [bad_claim])
    profit = calculate_attacker_profit(res)
    assert profit.goods_acquired == 0, "Invalid claims must not generate goods acquired"


# Regression 6: Offline-accepted claims can still represent goods acquired even when settlement later rejects duplicate permit claim
def test_offline_accepted_claims_count_as_goods_acquired_when_settlement_rejects_duplicate_permit():
    permit = Permit("p_1", "alw_1", "payer_1", "pk_1", 50000, 1000, "sig_1")
    allowance = Allowance("alw_1", "payer_1", 50000, 50000, 0, 1000, [permit])

    # Two valid offline claims on the same permit (double spend)
    c1 = Claim(
        tx_uuid="tx_1",
        allowance_id="alw_1",
        permit_id="p_1",
        payer_id="payer_1",
        payee_id="merchant_a",
        amount=50000,
        ingestion_sequence=1,
        submission_time=1001,
        claim_type=ClaimType.HONEST_MERCHANT,
        offline_accepted=True,
    )
    c2 = Claim(
        tx_uuid="tx_2",
        allowance_id="alw_1",
        permit_id="p_1",
        payer_id="payer_1",
        payee_id="merchant_b",
        amount=50000,
        ingestion_sequence=2,
        submission_time=1002,
        claim_type=ClaimType.HONEST_MERCHANT,
        offline_accepted=True,
    )

    res = FirstClaimSettlement().settle(allowance, [c1, c2])
    assert res.claim_results[0].status == SettlementStatus.SETTLED_FULL
    assert res.claim_results[1].status == SettlementStatus.REJECTED  # Duplicate permit rejected by FC
    assert res.claim_results[1].validation_passed is True

    profit = calculate_attacker_profit(res)
    assert profit.goods_acquired == 100000, "Both offline-accepted claims represent goods acquired"

    # If c2 was NOT accepted offline (offline_accepted = False)
    c2_not_accepted = Claim(
        tx_uuid="tx_2_no_pos",
        allowance_id="alw_1",
        permit_id="p_1",
        payer_id="payer_1",
        payee_id="merchant_b",
        amount=50000,
        ingestion_sequence=2,
        submission_time=1002,
        claim_type=ClaimType.HONEST_MERCHANT,
        offline_accepted=False,
    )
    res2 = FirstClaimSettlement().settle(allowance, [c1, c2_not_accepted])
    profit2 = calculate_attacker_profit(res2)
    assert profit2.goods_acquired == 50000, "Only offline-accepted claim represents goods acquired"


# Regression 7: Mule count calculations are deterministic with boundary tests for 1, 2, 3, 5 receivers
def test_mule_count_calculations_deterministic_boundary():
    # 1 receiver boundary
    assert calculate_mule_count(1, 0) == 0
    assert calculate_mule_count(1, 10) == 0
    assert calculate_mule_count(1, 25) == 0
    assert calculate_mule_count(1, 50) == 1
    assert calculate_mule_count(1, 75) == 1
    assert calculate_mule_count(1, 100) == 1

    # 2 receivers boundary
    assert calculate_mule_count(2, 0) == 0
    assert calculate_mule_count(2, 10) == 0
    assert calculate_mule_count(2, 25) == 1
    assert calculate_mule_count(2, 50) == 1
    assert calculate_mule_count(2, 75) == 2
    assert calculate_mule_count(2, 100) == 2

    # 3 receivers boundary
    assert calculate_mule_count(3, 0) == 0
    assert calculate_mule_count(3, 10) == 0
    assert calculate_mule_count(3, 25) == 1
    assert calculate_mule_count(3, 50) == 2
    assert calculate_mule_count(3, 75) == 2
    assert calculate_mule_count(3, 100) == 3

    # 5 receivers boundary
    assert calculate_mule_count(5, 0) == 0
    assert calculate_mule_count(5, 10) == 1
    assert calculate_mule_count(5, 25) == 1
    assert calculate_mule_count(5, 50) == 3
    assert calculate_mule_count(5, 75) == 4
    assert calculate_mule_count(5, 100) == 5

    # Determinism verification (repeated runs must be identical)
    for _ in range(50):
        assert calculate_mule_count(5, 50) == 3
        assert calculate_mule_count(3, 25) == 1


# Regression 8: FC, PR and PL still reproduce the initial baseline results
def test_fc_pr_pl_reproduce_initial_baseline_results():
    outcomes = run_initial_experiment()

    # FC
    fc = outcomes["FC"]
    assert fc.mule_payout_paise == 50000
    assert fc.merchant_a_payout_paise == 0
    assert fc.merchant_b_payout_paise == 0
    assert fc.total_payout_paise == 50000
    assert fc.honest_recovery_rate == 0.0
    assert fc.attacker_net_profit_paise == 100000

    # PR
    pr = outcomes["PR"]
    assert pr.mule_payout_paise == 33334
    assert pr.merchant_a_payout_paise == 33333
    assert pr.merchant_b_payout_paise == 33333
    assert pr.total_payout_paise == 100000
    assert pytest.approx(pr.honest_recovery_rate, 1e-4) == 0.6667
    assert pr.attacker_net_profit_paise == 33334

    # PL
    pl = outcomes["PL"]
    assert pl.mule_payout_paise == 50000
    assert pl.merchant_a_payout_paise == 50000
    assert pl.merchant_b_payout_paise == 0
    assert pl.total_payout_paise == 100000
    assert pl.honest_recovery_rate == 0.50
    assert pl.attacker_net_profit_paise == 50000
