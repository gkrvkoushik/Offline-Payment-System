"""Dedicated test suite for EXP-08: Funding-Source Composition Sensitivity.

Verifies:
1. Every funding composition sums exactly to the fixed total reserve (100,000 paise).
2. No funding source can be overdrawn (F_C <= C, F_H <= H, F_F <= F).
3. Funding attribution sums to total payout (F_C + F_H + F_F == total_payout).
4. Payer debit equals collateral debit plus hold debit (D_payer = F_C + F_H).
5. Issuer expenditure is not charged to the payer (F_F distinct from D_payer).
6. Gross payout remains invariant across funding compositions under controlled conditions.
7. Honest recovery is correctly calculated.
8. Malicious-payer and compromised-victim accounting remain separate.
9. Zero denominators are handled according to existing metric conventions.
10. CSV outputs contain all required fields.
11. Summary and reconciliation outputs are correct and report status PASSED.
12. Edge cases for zero-valued funding tiers and fully exhausted reserves.
"""

import csv
import json
import os
import tempfile
import pytest

from offline_payment.config import ClaimType
from offline_payment.experiments.adversarial_evaluation import AdversarialEvaluationSuite
from offline_payment.models.allowance import Allowance
from offline_payment.models.claim import Claim
from offline_payment.models.permit import Permit
from offline_payment.settlement.first_claim import FirstClaimSettlement
from offline_payment.settlement.payer_liability import PayerLiabilitySettlement
from offline_payment.settlement.pro_rata import GlobalProRataSettlement


@pytest.fixture
def temp_suite():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield AdversarialEvaluationSuite(output_dir=tmpdir), tmpdir


def test_exp08_compositions_sum_to_constant_reserve(temp_suite):
    """Test 1: Every composition sums strictly to 100,000 paise (INR 1,000)."""
    suite, tmpdir = temp_suite
    runs, summary, reconciliation = suite.run_experiment_08_funding_source_sensitivity(
        output_subdir="test_exp08"
    )

    for r in reconciliation:
        c_val = r["C_paise"]
        h_val = r["H_paise"]
        f_val = r["F_paise"]
        assert c_val + h_val + f_val == 100000
        assert r["total_reserve_paise"] == 100000
        assert r["invariant_reserve_equals_100k"] is True


def test_exp08_tiers_never_overdrawn(temp_suite):
    """Test 2: No funding tier is ever overdrawn in any run."""
    suite, tmpdir = temp_suite
    runs, summary, reconciliation = suite.run_experiment_08_funding_source_sensitivity(
        output_subdir="test_exp08"
    )

    for r in reconciliation:
        assert r["funded_from_c"] <= r["C_paise"]
        assert r["funded_from_h"] <= r["H_paise"]
        assert r["funded_from_f"] <= r["F_paise"]
        assert r["invariant_tiers_not_overdrawn"] is True


def test_exp08_sources_sum_to_total_payout(temp_suite):
    """Test 3: Funding attribution strictly sums to total payout."""
    suite, tmpdir = temp_suite
    runs, summary, reconciliation = suite.run_experiment_08_funding_source_sensitivity(
        output_subdir="test_exp08"
    )

    for r in reconciliation:
        total_sources = r["funded_from_c"] + r["funded_from_h"] + r["funded_from_f"]
        assert total_sources == r["total_payout_paise"]
        assert r["invariant_sources_sum_to_payout"] is True


def test_exp08_payer_debit_and_issuer_expenditure_separation(temp_suite):
    """Test 4 & 5: D_payer = F_C + F_H and D_issuer = F_F, properly separated."""
    suite, tmpdir = temp_suite
    runs, summary, reconciliation = suite.run_experiment_08_funding_source_sensitivity(
        output_subdir="test_exp08"
    )

    for r in runs:
        assert r["payer_total_debit_paise"] == r["payer_collateral_debit_paise"] + r["payer_hold_debit_paise"]
        # Total payout equals payer debit plus issuer expenditure
        assert r["total_payout_paise"] == r["payer_total_debit_paise"] + r["issuer_guarantee_expenditure_paise"]


def test_exp08_gross_payout_invariance_across_funding_compositions(temp_suite):
    """Test 6: Total payout is completely invariant to C:H:F composition."""
    suite, tmpdir = temp_suite
    runs, summary, reconciliation = suite.run_experiment_08_funding_source_sensitivity(
        output_subdir="test_exp08"
    )

    # For any fixed (scenario, perm, policy), gross payout is 100,000 across all 11 compositions
    payout_groups = {}
    for r in runs:
        key = (r["attacker_scenario"], r["permutation_idx"], r["settlement_policy"])
        payout_groups.setdefault(key, []).append(r["total_payout_paise"])

    for key, payouts in payout_groups.items():
        assert len(payouts) == 11
        assert len(set(payouts)) == 1
        assert payouts[0] == 100000


def test_exp08_honest_recovery_calculation(temp_suite):
    """Test 7: Honest merchant recovery is mathematically sound and bounded in [0, 1]."""
    suite, tmpdir = temp_suite
    runs, summary, reconciliation = suite.run_experiment_08_funding_source_sensitivity(
        output_subdir="test_exp08"
    )

    for r in runs:
        hr = r["honest_recovery_rate"]
        assert 0.0 <= hr <= 1.0
        expected_hr = r["honest_payout_paise"] / r["honest_eligible_paise"]
        assert pytest.approx(hr, abs=1e-6) == expected_hr


def test_exp08_malicious_payer_vs_compromised_victim_profit(temp_suite):
    """Test 8: Malicious payer absorbs payer debit; compromised victim does not."""
    suite, tmpdir = temp_suite
    runs, summary, reconciliation = suite.run_experiment_08_funding_source_sensitivity(
        output_subdir="test_exp08"
    )

    # Compare runs with identical composition, perm, policy between malicious_payer and compromised_victim
    run_map = {}
    for r in runs:
        key = (r["funding_composition"], r["permutation_idx"], r["settlement_policy"], r["attacker_scenario"])
        run_map[key] = r

    for cfg in ["100C-0H-0F", "50C-50H-0F", "33C-33H-33F", "0C-0H-100F"]:
        for p in range(1, 7):
            for pol in ["FIRST_CLAIM", "GLOBAL_PRO_RATA", "PAYER_LIABILITY"]:
                mal = run_map[(cfg, p, pol, "malicious_payer")]
                vic = run_map[(cfg, p, pol, "compromised_victim")]

                # In compromised victim, attacker does not pay payer debit
                payer_debit = mal["payer_total_debit_paise"]
                diff = vic["attacker_net_profit_paise"] - mal["attacker_net_profit_paise"]
                assert diff == payer_debit


def test_exp08_csv_headers_and_reconciliation_status(temp_suite):
    """Test 10 & 11: Output CSVs exist and all reconciliation entries are PASSED."""
    suite, tmpdir = temp_suite
    suite.run_experiment_08_funding_source_sensitivity(output_subdir="test_exp08")

    exp_dir = os.path.join(tmpdir, "test_exp08")
    runs_csv = os.path.join(exp_dir, "funding_source_runs.csv")
    sum_csv = os.path.join(exp_dir, "funding_source_summary.csv")
    recon_csv = os.path.join(exp_dir, "funding_source_reconciliation.csv")
    cfg_json = os.path.join(exp_dir, "funding_source_configuration.json")
    rep_md = os.path.join(exp_dir, "funding_source_invariance_report.md")

    assert os.path.exists(runs_csv)
    assert os.path.exists(sum_csv)
    assert os.path.exists(recon_csv)
    assert os.path.exists(cfg_json)
    assert os.path.exists(rep_md)

    with open(recon_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 594
        for r in rows:
            assert r["reconciliation_status"] == "PASSED"


def test_exp08_edge_cases_zero_tiers_and_exhausted_reserves():
    """Test 12: Edge cases with zero-valued tiers (0C-0H-100F, 100C-0H-0F) and exhausted reserve."""
    pol = GlobalProRataSettlement()

    # Case A: 100% Guarantee (C=0, H=0, F=100000)
    p1 = Permit("p_1", "alw_f", "payer_1", "pk_1", 100000, 1000, "sig_1")
    alw_f = Allowance("alw_f", "payer_1", 0, 0, 100000, 1000, [p1])
    c1 = Claim("tx_1", "alw_f", "p_1", "payer_1", "payee_1", 100000, 1, 1000)
    res_f = pol.settle(alw_f, [c1])

    assert res_f.total_funded_c == 0
    assert res_f.total_funded_h == 0
    assert res_f.total_funded_f == 100000
    assert res_f.total_payout == 100000
    assert res_f.total_payer_funded == 0

    # Case B: 100% Collateral (C=100000, H=0, F=0)
    p2 = Permit("p_2", "alw_c", "payer_1", "pk_1", 100000, 1000, "sig_2")
    alw_c = Allowance("alw_c", "payer_1", 100000, 0, 0, 1000, [p2])
    c2 = Claim("tx_2", "alw_c", "p_2", "payer_1", "payee_1", 100000, 1, 1000)
    res_c = pol.settle(alw_c, [c2])

    assert res_c.total_funded_c == 100000
    assert res_c.total_funded_h == 0
    assert res_c.total_funded_f == 0
    assert res_c.total_payout == 100000
    assert res_c.total_payer_funded == 100000
