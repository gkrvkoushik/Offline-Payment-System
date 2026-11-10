"""Simulation runner to coordinate and execute research experiments."""

import os
from typing import Dict

from offline_payment.experiments.policy_comparison import run_initial_experiment, InitialExperimentOutcome
from offline_payment.experiments.reserve_coverage import run_reserve_coverage_experiment
from offline_payment.experiments.receiver_sweep import run_receiver_sweep_experiment
from offline_payment.experiments.denomination import run_denomination_and_funding_experiment
from offline_payment.experiments.multiseed import run_multiseed_experiment
from offline_payment.experiments.blockchain_performance import run_blockchain_performance_experiment
from offline_payment.metrics.telemetry import TelemetryLogger
from offline_payment.visualization.plots import generate_all_graphs


def print_initial_experiment_table(outcomes: Dict[str, InitialExperimentOutcome]) -> None:
    """Print the verified initial experiment results in a clean research table."""
    print("\n" + "=" * 80)
    print("INITIAL REPRODUCIBLE EXPERIMENT RESULTS (BASELINE CONFIGURATION)")
    print("Configuration: C = INR 500, H = INR 500, F = INR 0 -> Reserve S = INR 1,000")
    print("Claims: 1 Mule (INR 500), 2 Honest Merchants (INR 500 each) -> Total = INR 1,500")
    print("Ingestion sequence: Mule (1) -> Merchant A (2) -> Merchant B (3)")
    print("=" * 80)
    print(f"{'Policy':<8} | {'Mule Payout':<14} | {'Merchant A':<14} | {'Merchant B':<14} | {'Total Payout':<14} | {'Honest Rec':<10} | {'Attacker Profit'}")
    print("-" * 80)

    for pol in ["FC", "PR", "PL"]:
        o = outcomes[pol]
        honest_rec_str = (
            f"{o.honest_recovery_rate * 100:>9.1f}%"
            if o.honest_recovery_rate is not None
            else f"{'N/A':>10}"
        )
        print(
            f"{o.policy:<8} | "
            f"INR {o.mule_payout_inr:>10.2f} | "
            f"INR {o.merchant_a_inr:>10.2f} | "
            f"INR {o.merchant_b_inr:>10.2f} | "
            f"INR {o.total_payout_inr:>10.2f} | "
            f"{honest_rec_str} | "
            f"INR {o.attacker_profit_inr:>12.2f}"
        )
    print("=" * 80 + "\n")


def run_all_simulations(results_dir: str = "results") -> None:
    """Execute all research experiments, telemetry collection, and graph generation."""
    os.makedirs(results_dir, exist_ok=True)
    logger = TelemetryLogger()

    print("[1/5] Running Initial Reproducible Experiment...")
    initial_csv = os.path.join(results_dir, "initial_experiment.csv")
    outcomes = run_initial_experiment(output_csv_path=initial_csv, logger=logger)
    print_initial_experiment_table(outcomes)
    print(f"      Saved initial experiment to: {initial_csv}")

    print("[2/5] Running Reserve Coverage Sweep (S/X ratio sensitivity)...")
    cov_rows = run_reserve_coverage_experiment(output_dir=results_dir, logger=logger)
    print(f"      Completed {len(cov_rows)} configurations -> {results_dir}/reserve_coverage_summary.csv")

    print("[3/5] Running Receiver Count, Mule Share, & Position Sweep...")
    rec_rows = run_receiver_sweep_experiment(output_dir=results_dir, logger=logger)
    print(f"      Completed {len(rec_rows)} configurations -> {results_dir}/receiver_sweep_summary.csv")

    print("[4/5] Running Controlled Denomination Granularity Experiment...")
    den_rows = run_denomination_and_funding_experiment(output_dir=results_dir, logger=logger)
    print(f"      Completed {len(den_rows)} configurations -> {results_dir}/denomination_summary.csv")

    print("[5/6] Running Multi-Seed Randomized Simulation...")
    seed_rows = run_multiseed_experiment(output_dir=results_dir, logger=logger)
    print(f"      Completed {len(seed_rows)} policy aggregates -> {results_dir}/multiseed_summary.csv")

    print("[6/6] Running Blockchain Audit Anchoring & Merkle Scaling Benchmarks...")
    bench_rows = run_blockchain_performance_experiment(output_dir=results_dir)
    print(f"      Completed {len(bench_rows)} scale configurations -> {results_dir}/blockchain_performance_summary.csv")

    # Export Permit Inventory, Attack Events, and Audit Anchors Telemetry
    permit_inv_csv = os.path.join(results_dir, "permit_inventory.csv")
    logger.export_permit_inventory_csv(permit_inv_csv)
    print(f"\n[Telemetry] Exported complete permit inventory -> {permit_inv_csv} ({len(logger.permit_records)} permits)")

    attack_events_csv = os.path.join(results_dir, "attack_events.csv")
    logger.export_attack_events_csv(attack_events_csv)
    print(f"[Telemetry] Exported attack events & POS acceptance -> {attack_events_csv} ({len(logger.attack_records)} events)")

    audit_anchors_csv = os.path.join(results_dir, "audit_anchors.csv")
    logger.export_audit_anchors_csv(audit_anchors_csv)
    print(f"[Telemetry] Exported blockchain audit anchors -> {audit_anchors_csv} ({len(logger.anchor_records)} batches anchored)")

    # Generate comparative graphs
    print("\n[Visualization] Generating comparative graphs for FC, PR, and PL...")
    graphs = generate_all_graphs(results_dir=results_dir)
    for g in graphs:
        print(f"      Created graph: {g}")

    print("\nAll experiments, telemetry datasets, and graphs successfully generated in 'results/'.")
