"""Automated tests for permit inventory, attack events, multi-seed experiments, and visualization."""

import csv
import os
import pytest

from offline_payment.metrics.telemetry import TelemetryLogger
from offline_payment.experiments.multiseed import run_multiseed_experiment
from offline_payment.visualization.plots import generate_all_graphs
from offline_payment.simulation.runner import run_all_simulations


def test_permit_inventory_csv_deliverable(tmp_path):
    out_dir = str(tmp_path)
    run_all_simulations(results_dir=out_dir)

    inv_path = os.path.join(out_dir, "permit_inventory.csv")
    assert os.path.exists(inv_path), "permit_inventory.csv must exist"

    with open(inv_path, encoding="utf-8") as f:
        records = list(csv.DictReader(f))

    assert len(records) > 0, "permit_inventory.csv must not be empty"

    # Verify presence of unused permits
    statuses = set(r["permit_status"] for r in records)
    assert "UNUSED" in statuses, "permit_inventory.csv must include unused permits"
    assert "DOUBLE_SPENT" in statuses, "permit_inventory.csv must include double spent permits"

    for r in records:
        assert "allowance_id" in r
        assert "permit_id" in r
        assert "denomination_paise" in r
        assert "is_used" in r
        assert "is_double_spent" in r
        assert "stranded_paise" in r
        assert int(r["denomination_paise"]) > 0


def test_attack_events_csv_deliverable(tmp_path):
    out_dir = str(tmp_path)
    run_all_simulations(results_dir=out_dir)

    events_path = os.path.join(out_dir, "attack_events.csv")
    assert os.path.exists(events_path), "attack_events.csv must exist"

    with open(events_path, encoding="utf-8") as f:
        events = list(csv.DictReader(f))

    assert len(events) > 0, "attack_events.csv must not be empty"

    for e in events:
        assert "attacker_id" in e
        assert "attacker_controls_payer" in e
        assert "attacker_controls_payee" in e
        assert "payer_is_victim" in e
        assert "pos_validation_passed" in e
        assert "offline_accepted" in e
        assert "goods_released" in e
        assert "centre_validation_passed" in e
        assert "settlement_eligible" in e
        assert "goods_release_value_paise" in e
        assert "recoverable_mule_credit_paise" in e
        assert "payer_owned_debit_paise" in e
        assert "issuer_expenditure_paise" in e
        assert "attack_costs_paise" in e
        assert "attacker_gross_benefit_paise" in e
        assert "attacker_net_profit_paise" in e

        # Goods released invariant: only honest merchants that accepted offline release goods
        if e["goods_released"] == "True":
            assert e["claim_type"] == "HONEST_MERCHANT"
            assert e["offline_accepted"] == "True"
            assert int(e["goods_release_value_paise"]) > 0
        else:
            assert int(e["goods_release_value_paise"]) == 0

        # Mule credit invariant: only mule accounts can recover mule credit
        if int(e["mule_credit_paise"]) > 0:
            assert e["claim_type"] in ("MULE", "ATTACKER_SELF")
            assert int(e["paid_paise"]) > 0


def test_reproducible_multiseed_experiments(tmp_path):
    out_dir = str(tmp_path)
    seeds = [42, 101, 777]

    # Run twice with identical seeds
    res1 = run_multiseed_experiment(seeds=seeds, output_dir=os.path.join(out_dir, "run1"))
    res2 = run_multiseed_experiment(seeds=seeds, output_dir=os.path.join(out_dir, "run2"))

    assert len(res1) == len(res2) == 3  # FC, PR, PL
    for r1, r2 in zip(res1, res2):
        assert r1["policy"] == r2["policy"]
        assert r1["mean_payout_paise"] == r2["mean_payout_paise"]
        assert r1["mean_honest_recovery_rate"] == r2["mean_honest_recovery_rate"]
        assert r1["std_honest_recovery_rate"] == r2["std_honest_recovery_rate"]
        assert r1["mean_attacker_profit_paise"] == r2["mean_attacker_profit_paise"]


def test_comparison_graphs_generation(tmp_path):
    out_dir = str(tmp_path)
    run_all_simulations(results_dir=out_dir)

    graphs_dir = os.path.join(out_dir, "graphs")
    assert os.path.exists(graphs_dir)

    expected_graphs = [
        "baseline_comparison.png",
        "denomination_granularity_comparison.png",
        "receiver_sweep_comparison.png",
        "multiseed_distribution.png",
        "blockchain_performance_scaling.png",
    ]
    for g in expected_graphs:
        g_path = os.path.join(graphs_dir, g)
        assert os.path.exists(g_path), f"Graph {g} must be generated"
        assert os.path.getsize(g_path) > 1000, f"Graph {g} must have non-trivial size"


def test_audit_anchors_csv_deliverable(tmp_path):
    out_dir = str(tmp_path)
    run_all_simulations(results_dir=out_dir)

    anchors_path = os.path.join(out_dir, "audit_anchors.csv")
    assert os.path.exists(anchors_path), "audit_anchors.csv must exist"

    with open(anchors_path, encoding="utf-8") as f:
        records = list(csv.DictReader(f))

    assert len(records) > 0, "audit_anchors.csv must contain anchored batches"
    for r in records:
        assert "batch_id" in r
        assert "merkle_root" in r
        assert "transaction_hash" in r
        assert "block_number" in r
        assert "actual_gas_used" in r
        assert "receipt_status" in r
        assert "chain_id" in r
        assert "contract_address" in r
        assert "contract_version" in r
        assert "execution_environment" in r
        assert r["status"] == "ANCHORED"
        assert len(r["merkle_root"]) == 64
        assert int(r["actual_gas_used"]) > 0
