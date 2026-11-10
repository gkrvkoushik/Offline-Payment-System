"""Mathematical reconciliation and invariant tests for settlement and audit evidence."""

import csv
import os
import pytest
from offline_payment.attacks.comprehensive_scenarios import (
    build_scenario_malicious_payer_mule,
    build_scenario_malicious_payer_honest,
    build_scenario_cloned_key_victim,
    build_scenario_independent_mule,
    build_scenario_mixed_honest_and_mule,
)
from offline_payment.models.allowance import Allowance
from offline_payment.models.permit import Permit
from offline_payment.settlement.first_claim import FirstClaimSettlement
from offline_payment.settlement.pro_rata import GlobalProRataSettlement
from offline_payment.settlement.payer_liability import PayerLiabilitySettlement
from offline_payment.simulation.runner import run_all_simulations


@pytest.fixture(scope="module")
def run_simulation(tmp_path_factory):
    out_dir = str(tmp_path_factory.mktemp("reconciliation_results"))
    run_all_simulations(results_dir=out_dir)
    return out_dir


def test_reconciliation_audit_anchors(run_simulation):
    out_dir = run_simulation
    anchors_csv = os.path.join(out_dir, "audit_anchors.csv")
    assert os.path.exists(anchors_csv)

    with open(anchors_csv, encoding="utf-8") as f:
        records = list(csv.DictReader(f))

    assert len(records) > 0
    for r in records:
        assert len(r["batch_id"]) > 0
        assert len(r["merkle_root"]) == 64
        assert int(r["actual_gas_used"]) > 0
        assert int(r["block_number"]) >= 1000
        assert r["execution_environment"] in ("MOCK_SIMULATED_EVM", "REAL_LOCAL_JSONRPC_EVM")


def test_reconciliation_financial_payouts(run_simulation):
    out_dir = run_simulation
    events_csv = os.path.join(out_dir, "attack_events.csv")
    assert os.path.exists(events_csv)

    with open(events_csv, encoding="utf-8") as f:
        events = list(csv.DictReader(f))

    assert len(events) > 0
    for e in events:
        req = int(e["requested_paise"])
        paid = int(e["paid_paise"])
        fc = int(e["funded_c_paise"])
        fh = int(e["funded_h_paise"])
        ff = int(e["funded_f_paise"])

        # Invariant 1: Sum of funding tiers strictly equals payout
        assert fc + fh + ff == paid, f"Funding tiers mismatch for tx {e['tx_uuid']}"
        # Invariant 2: Payout never exceeds requested amount
        assert paid <= req, f"Payout {paid} exceeds requested {req}"
        assert paid >= 0, f"Negative payout for tx {e['tx_uuid']}"


def test_reconciliation_attacker_economics(run_simulation):
    out_dir = run_simulation
    events_csv = os.path.join(out_dir, "attack_events.csv")

    with open(events_csv, encoding="utf-8") as f:
        events = list(csv.DictReader(f))

    for e in events:
        goods_val = int(e["goods_release_value_paise"])
        mule_credit = int(e["recoverable_mule_credit_paise"])
        payer_debit = int(e["payer_owned_debit_paise"])
        attack_costs = int(e["attack_costs_paise"])
        gross_benefit = int(e["attacker_gross_benefit_paise"])
        net_profit = int(e["attacker_net_profit_paise"])

        # Invariant 3: Gross benefit = goods release + mule credit
        assert gross_benefit == goods_val + mule_credit

        # Invariant 4: Net profit formulation according to control role
        ctrl_payer = (e["attacker_controls_payer"] == "True")
        payer_victim = (e["payer_is_victim"] == "True")

        if ctrl_payer:
            expected_net = gross_benefit - payer_debit - attack_costs
        elif payer_victim:
            expected_net = gross_benefit - attack_costs
        else:
            expected_net = mule_credit - attack_costs

        assert net_profit == expected_net, f"Net profit mismatch for tx {e['tx_uuid']}"


@pytest.mark.parametrize("policy_cls", [FirstClaimSettlement, GlobalProRataSettlement, PayerLiabilitySettlement])
def test_all_five_attack_scenarios(policy_cls):
    policy = policy_cls()
    allowance = Allowance(
        allowance_id="alw_scenarios",
        payer_id="payer_alice",
        allowance_amount=50000,
        payer_hold=50000,
        issuer_guarantee=0,
        settlement_deadline=1800000000,
    )
    permit = Permit(
        permit_id="pmt_scen_1",
        allowance_id="alw_scenarios",
        payer_id="payer_alice",
        payer_public_key="pub_alice",
        denomination=50000,
        settlement_deadline=1800000000,
        issuer_signature="sig_issuer",
    )
    allowance.permits = [permit]

    # Scenario 1: Malicious payer controls mule account
    c1 = build_scenario_malicious_payer_mule(allowance, permit)
    res1 = policy.settle(allowance, c1)
    assert res1.total_payout <= allowance.total_reserve

    # Scenario 2: Malicious payer attacks honest merchants
    c2 = build_scenario_malicious_payer_honest(allowance, permit)
    res2 = policy.settle(allowance, c2)
    assert res2.total_payout <= allowance.total_reserve

    # Scenario 3: Legitimate payer is victim of cloned credentials
    c3 = build_scenario_cloned_key_victim(allowance, permit)
    res3 = policy.settle(allowance, c3)
    assert res3.total_payout <= allowance.total_reserve

    # Scenario 4: Independent mule account
    c4 = build_scenario_independent_mule(allowance, permit)
    res4 = policy.settle(allowance, c4)
    assert res4.total_payout <= allowance.total_reserve

    # Scenario 5: Mixed honest and mule payees
    c5 = build_scenario_mixed_honest_and_mule(allowance, permit)
    res5 = policy.settle(allowance, c5)
    assert res5.total_payout <= allowance.total_reserve
