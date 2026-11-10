"""Unit and regression tests for the controlled denomination granularity experiment."""

import csv
import os
import pytest

from offline_payment.models.allowance import Allowance
from offline_payment.models.permit import Permit
from offline_payment.validation.claim_validator import ClaimValidator
from offline_payment.settlement.first_claim import FirstClaimSettlement
from offline_payment.settlement.pro_rata import GlobalProRataSettlement
from offline_payment.settlement.payer_liability import PayerLiabilitySettlement
from offline_payment.experiments.denomination import (
    TOTAL_ALLOWANCE_PAISE,
    DENOMINATION_CONFIGS,
    FUNDING_CONFIGS,
    SCENARIO_NAMES,
    create_controlled_permits,
    generate_controlled_scenario_claims,
    run_denomination_and_funding_experiment,
)


# Test 1: Total permit value is invariant across denomination configurations
def test_total_permit_value_invariant_across_denomination_configs():
    for d_cfg in DENOMINATION_CONFIGS:
        permits = create_controlled_permits(d_cfg, allowance_id="alw_inv_test")
        total_val = sum(p.denomination for p in permits)
        assert total_val == TOTAL_ALLOWANCE_PAISE == 100000, (
            f"Config {d_cfg['name']} total permit value is {total_val}, expected 100000 paise"
        )
        if d_cfg["name"] == "Micro":
            assert len(permits) == 10
            assert all(p.denomination == 10000 for p in permits)
        elif d_cfg["name"] == "Standard":
            assert len(permits) == 2
            assert all(p.denomination == 50000 for p in permits)
        elif d_cfg["name"] == "Large":
            assert len(permits) == 1
            assert all(p.denomination == 100000 for p in permits)


# Test 2: Total requested value is invariant across comparable scenarios
def test_total_requested_value_invariant_across_comparable_scenarios():
    for s_name in SCENARIO_NAMES:
        claims_by_denom = {}
        for d_cfg in DENOMINATION_CONFIGS:
            denom_name = d_cfg["name"]
            allowance_id = f"alw_test_{s_name}_{denom_name}"
            permits = create_controlled_permits(d_cfg, allowance_id)
            claims = generate_controlled_scenario_claims(
                scenario_name=s_name,
                denom_name=denom_name,
                allowance_id=allowance_id,
                permits=permits,
            )
            claims_by_denom[denom_name] = claims

        micro_req = sum(c.amount for c in claims_by_denom["Micro"])
        std_req = sum(c.amount for c in claims_by_denom["Standard"])
        large_req = sum(c.amount for c in claims_by_denom["Large"])

        assert micro_req == std_req == large_req, (
            f"Scenario {s_name} requested values differ: Micro={micro_req}, Std={std_req}, Large={large_req}"
        )

        # For scenarios 2..7, ensure receiver counts and mule shares are identical
        if s_name != "1_honest_spending":
            assert len(claims_by_denom["Micro"]) == len(claims_by_denom["Standard"]) == len(claims_by_denom["Large"])
            mule_micro = sum(1 for c in claims_by_denom["Micro"] if c.claim_type.value == "MULE")
            mule_std = sum(1 for c in claims_by_denom["Standard"] if c.claim_type.value == "MULE")
            mule_large = sum(1 for c in claims_by_denom["Large"] if c.claim_type.value == "MULE")
            assert mule_micro == mule_std == mule_large


# Test 3: All claim-permit references are valid
def test_all_claim_permit_references_valid():
    for s_name in SCENARIO_NAMES:
        for d_cfg in DENOMINATION_CONFIGS:
            denom_name = d_cfg["name"]
            allowance_id = f"alw_valid_{s_name[:4]}_{denom_name}"
            permits = create_controlled_permits(d_cfg, allowance_id)
            permit_map = {p.permit_id: p for p in permits}

            allowance = Allowance(
                allowance_id=allowance_id,
                payer_id="payer_denom",
                allowance_amount=50000,
                payer_hold=50000,
                issuer_guarantee=0,
                settlement_deadline=1000,
                permits=permits,
            )
            claims = generate_controlled_scenario_claims(
                scenario_name=s_name,
                denom_name=denom_name,
                allowance_id=allowance_id,
                permits=permits,
            )

            validator = ClaimValidator(allowance)
            for c in claims:
                val_res = validator.validate_claim(c)
                assert val_res.is_valid is True, (
                    f"Claim {c.tx_uuid} in scenario {s_name} ({denom_name}) failed validation: {val_res.error_message}"
                )
                assert c.permit_id in permit_map
                assert c.amount <= permit_map[c.permit_id].denomination


# Test 4: No permit is accidentally duplicated in the permit inventory
def test_no_permit_accidentally_duplicated_in_inventory():
    for d_cfg in DENOMINATION_CONFIGS:
        permits = create_controlled_permits(d_cfg, allowance_id="alw_unique_inv")
        permit_ids = [p.permit_id for p in permits]
        assert len(permit_ids) == len(set(permit_ids)), f"Duplicate permit IDs found in {d_cfg['name']}"


# Test 5: FC, PR and PL produce reproducible results
def test_fc_pr_pl_produce_reproducible_results():
    d_cfg = DENOMINATION_CONFIGS[0]  # Micro
    allowance_id = "alw_repro_test"
    permits = create_controlled_permits(d_cfg, allowance_id)
    allowance = Allowance(allowance_id, "payer_denom", 50000, 50000, 0, 1000, permits)
    claims = generate_controlled_scenario_claims("3_multi_permit_single_duplicate", "Micro", allowance_id, permits)

    for policy_cls in [FirstClaimSettlement, GlobalProRataSettlement, PayerLiabilitySettlement]:
        res1 = policy_cls().settle(allowance, claims)
        res2 = policy_cls().settle(allowance, claims)

        assert res1.total_payout == res2.total_payout
        assert [c.paid_amount for c in res1.claim_results] == [c.paid_amount for c in res2.claim_results]
        assert [c.status for c in res1.claim_results] == [c.status for c in res2.claim_results]


# Test 6: Raw and summary CSV values reconcile
def test_raw_and_summary_csv_values_reconcile(tmp_path):
    out_dir = str(tmp_path)
    # Run a test slice with 2 scenarios and 1 funding config
    test_scenarios = ["1_honest_spending", "3_multi_permit_single_duplicate"]
    test_funding = [FUNDING_CONFIGS[0]]

    summary_rows = run_denomination_and_funding_experiment(
        funding_configs=test_funding,
        denom_configs=DENOMINATION_CONFIGS,
        scenario_names=test_scenarios,
        output_dir=out_dir,
    )

    summary_file = os.path.join(out_dir, "denomination_summary.csv")
    raw_file = os.path.join(out_dir, "denomination_raw.csv")

    assert os.path.exists(summary_file)
    assert os.path.exists(raw_file)

    with open(summary_file, encoding="utf-8") as f:
        summaries = list(csv.DictReader(f))
    with open(raw_file, encoding="utf-8") as f:
        raws = list(csv.DictReader(f))

    for s in summaries:
        s_name = s["scenario_name"]
        f_name = s["funding_config"]
        d_name = s["denomination_config"]
        pol = s["policy"]

        matching_raws = [
            r for r in raws
            if r["scenario_name"] == s_name
            and r["funding_config"] == f_name
            and r["denomination_config"] == d_name
            and r["policy"] == pol
        ]

        # Reconcile claims count
        assert len(matching_raws) == int(s["total_claims_count"])

        # Reconcile requested paise
        sum_requested = sum(int(r["requested_paise"]) for r in matching_raws)
        assert sum_requested == int(s["total_requested_paise"])

        # Reconcile payout paise
        sum_paid = sum(int(r["paid_paise"]) for r in matching_raws)
        assert sum_paid == int(s["total_payout_paise"])

        # Reconcile funding source breakdown
        sum_c = sum(int(r["funded_c_paise"]) for r in matching_raws)
        sum_h = sum(int(r["funded_h_paise"]) for r in matching_raws)
        sum_f = sum(int(r["funded_f_paise"]) for r in matching_raws)
        assert sum_c + sum_h + sum_f == sum_paid

        # Reconcile stranded value: Payout + Stranded == Total permit value (100000 paise)
        assert int(s["total_payout_paise"]) + int(s["stranded_permit_value_paise"]) == 100000
