"""Visualization module for generating publication-quality comparison graphs for FC, PR, and PL."""

import os
from typing import Dict, List, Optional
import csv

# Headless backend configuration for reliable sandbox execution
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def setup_matplotlib_env(cache_dir: str = "results/.mpl_cache") -> None:
    """Ensure matplotlib cache directory is writable."""
    os.makedirs(cache_dir, exist_ok=True)
    os.environ["MPLCONFIGDIR"] = os.path.abspath(cache_dir)


def plot_baseline_comparison(
    initial_csv: str = "results/initial_experiment.csv",
    output_png: str = "results/graphs/baseline_comparison.png",
) -> str:
    """Generate side-by-side comparison of Payouts, Recovery, and Profit under Baseline."""
    setup_matplotlib_env()
    os.makedirs(os.path.dirname(os.path.abspath(output_png)), exist_ok=True)

    policies = []
    mule_payouts = []
    merchant_payouts = []
    honest_recoveries = []
    attacker_profits = []

    with open(initial_csv, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            policies.append(r["policy"])
            mule_payouts.append(float(r["mule_payout_inr"]))
            # Sum of Merchant A + Merchant B
            merchant_payouts.append(float(r["merchant_a_inr"]) + float(r["merchant_b_inr"]))
            honest_recoveries.append(float(r["honest_recovery_rate"]) * 100)
            attacker_profits.append(float(r["attacker_profit_inr"]))

    x = np.arange(len(policies))
    width = 0.35

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    # Subplot 1: Payout Distribution (Stacked)
    ax1.bar(x, mule_payouts, width, label="Mule Payout (INR)", color="#d9534f")
    ax1.bar(x, merchant_payouts, width, bottom=mule_payouts, label="Honest Merchant Payout (INR)", color="#5cb85c")
    ax1.set_ylabel("Settlement Payout (INR)", fontsize=11)
    ax1.set_title("Payout Distribution by Policy", fontsize=12, fontweight="bold")
    ax1.set_xticks(x)
    ax1.set_xticklabels(policies, fontsize=11, fontweight="bold")
    ax1.legend(loc="upper right")
    ax1.grid(axis="y", linestyle="--", alpha=0.5)

    # Subplot 2: Honest Recovery & Attacker Profit
    ax2_twin = ax2.twinx()
    b1 = ax2.bar(x - width/2, honest_recoveries, width, label="Honest Recovery (%)", color="#0275d8")
    b2 = ax2_twin.bar(x + width/2, attacker_profits, width, label="Attacker Profit (INR)", color="#f0ad4e")

    ax2.set_ylabel("Honest Recovery Rate (%)", color="#0275d8", fontsize=11)
    ax2_twin.set_ylabel("Attacker Net Profit (INR)", color="#f0ad4e", fontsize=11)
    ax2.set_title("Honest Recovery vs. Attacker Net Profit", fontsize=12, fontweight="bold")
    ax2.set_xticks(x)
    ax2.set_xticklabels(policies, fontsize=11, fontweight="bold")
    ax2.set_ylim(0, 110)
    ax2.grid(axis="y", linestyle="--", alpha=0.5)

    plt.tight_layout()
    plt.savefig(output_png, dpi=300)
    plt.close()
    return output_png


def plot_denomination_granularity(
    denomination_summary_csv: str = "results/denomination_summary.csv",
    output_png: str = "results/graphs/denomination_granularity_comparison.png",
) -> str:
    """Plot impact of Micro vs Standard vs Large denomination on Honest Recovery & Stranded Value."""
    setup_matplotlib_env()
    os.makedirs(os.path.dirname(os.path.abspath(output_png)), exist_ok=True)

    # Focus on Scenario 3 (multi_permit_single_duplicate) under Balanced_Hold
    target_scenario = "3_multi_permit_single_duplicate"
    denoms = ["Micro", "Standard", "Large"]
    policies = ["FC", "PR", "PL"]

    # Map (denom, policy) -> (honest_recovery, stranded_inr)
    data = {}
    with open(denomination_summary_csv, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            if r["scenario_name"] == target_scenario and r["funding_config"] == "Balanced_Hold":
                data[(r["denomination_config"], r["policy"])] = (
                    float(r["honest_recovery_rate"]) * 100 if r["honest_recovery_rate"] != "N/A" else 0.0,
                    float(r["stranded_permit_value_inr"]),
                )

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))

    x = np.arange(len(denoms))
    bar_width = 0.25
    colors = {"FC": "#d9534f", "PR": "#0275d8", "PL": "#5cb85c"}

    for idx, pol in enumerate(policies):
        rec_vals = [data.get((d, pol), (0, 0))[0] for d in denoms]
        ax1.bar(x + idx * bar_width, rec_vals, bar_width, label=pol, color=colors[pol])

    ax1.set_ylabel("Honest Receiver Recovery (%)", fontsize=11)
    ax1.set_title("Honest Recovery across Denominations (1 Duplicate Permit)", fontsize=12, fontweight="bold")
    ax1.set_xticks(x + bar_width)
    ax1.set_xticklabels(denoms, fontsize=11, fontweight="bold")
    ax1.set_ylim(0, 110)
    ax1.legend(title="Policy")
    ax1.grid(axis="y", linestyle="--", alpha=0.5)

    for idx, pol in enumerate(policies):
        stranded_vals = [data.get((d, pol), (0, 0))[1] for d in denoms]
        ax2.bar(x + idx * bar_width, stranded_vals, bar_width, label=pol, color=colors[pol])

    ax2.set_ylabel("Stranded Permit Reserve (INR)", fontsize=11)
    ax2.set_title("Stranded Permit Value across Denominations", fontsize=12, fontweight="bold")
    ax2.set_xticks(x + bar_width)
    ax2.set_xticklabels(denoms, fontsize=11, fontweight="bold")
    ax2.legend(title="Policy")
    ax2.grid(axis="y", linestyle="--", alpha=0.5)

    plt.tight_layout()
    plt.savefig(output_png, dpi=300)
    plt.close()
    return output_png


def plot_receiver_sweep_comparison(
    receiver_summary_csv: str = "results/receiver_sweep_summary.csv",
    output_png: str = "results/graphs/receiver_sweep_comparison.png",
) -> str:
    """Plot recovery rate and attacker profit across receiver counts under FC, PR, PL."""
    setup_matplotlib_env()
    os.makedirs(os.path.dirname(os.path.abspath(output_png)), exist_ok=True)

    policies = ["FC", "PR", "PL"]
    colors = {"FC": "#d9534f", "PR": "#0275d8", "PL": "#5cb85c"}

    with open(receiver_summary_csv, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # Determine unique receiver counts present for 50% mule share, first position
    matching_all = [
        r for r in rows
        if int(r["mule_share_pct"]) == 50
        and r["mule_position"] == "first"
    ]

    rec_counts_set = set(int(r["num_receivers"]) for r in matching_all)
    rec_counts = sorted(list(rec_counts_set))

    # Assert all 3 policies exist for every receiver count
    data_rec = {pol: [] for pol in policies}
    data_profit = {pol: [] for pol in policies}

    for n in rec_counts:
        for pol in policies:
            matched = [
                r for r in matching_all
                if int(r["num_receivers"]) == n and r["policy"] == pol
            ]
            assert len(matched) > 0, f"Expected receiver count {n} for policy {pol} in {receiver_summary_csv}"
            r = matched[0]
            rec = float(r["honest_recovery_rate"]) * 100.0 if r["honest_recovery_rate"] != "N/A" else None
            profit = float(r["attacker_profit_inr"])
            data_rec[pol].append(rec)
            data_profit[pol].append(profit)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))

    for pol in policies:
        # Filter None for honest plotting without fabricating zeros
        valid_pairs = [(x, y) for x, y in zip(rec_counts, data_rec[pol]) if y is not None]
        if valid_pairs:
            vx, vy = zip(*valid_pairs)
            ax1.plot(vx, vy, marker="o", linewidth=2.2, label=pol, color=colors[pol])

    ax1.set_xlabel("Number of Receivers (50% Mule Share, Mule Ingested First)", fontsize=11)
    ax1.set_ylabel("Honest Recovery Rate (%)", fontsize=11)
    ax1.set_title("Honest Recovery vs Receiver Scaling", fontsize=12, fontweight="bold")
    ax1.set_ylim(-5, 105)
    ax1.set_xticks(rec_counts)
    ax1.legend(title="Policy")
    ax1.grid(True, linestyle="--", alpha=0.5)

    for pol in policies:
        ax2.plot(rec_counts, data_profit[pol], marker="s", linewidth=2.2, label=pol, color=colors[pol])

    ax2.set_xlabel("Number of Receivers (50% Mule Share, Mule Ingested First)", fontsize=11)
    ax2.set_ylabel("Attacker Net Profit (INR)", fontsize=11)
    ax2.set_title("Attacker Net Profit vs Receiver Scaling", fontsize=12, fontweight="bold")
    ax2.set_xticks(rec_counts)
    ax2.legend(title="Policy")
    ax2.grid(True, linestyle="--", alpha=0.5)

    plt.tight_layout()
    plt.savefig(output_png, dpi=300)
    plt.close()
    return output_png


def plot_multiseed_distribution(
    multiseed_summary_csv: str = "results/multiseed_summary.csv",
    output_png: str = "results/graphs/multiseed_distribution.png",
) -> str:
    """Plot multi-seed statistical mean and error bars across deterministic random seeds."""
    setup_matplotlib_env()
    os.makedirs(os.path.dirname(os.path.abspath(output_png)), exist_ok=True)

    policies = []
    mean_honest = []
    std_honest = []
    mean_profits = []
    std_profits = []

    with open(multiseed_summary_csv, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            policies.append(r["policy"])
            mean_honest.append(float(r["mean_honest_recovery_rate"]) * 100)
            std_honest.append(float(r["std_honest_recovery_rate"]) * 100)
            mean_profits.append(float(r["mean_attacker_profit_inr"]))
            std_profits.append(float(r["std_attacker_profit_inr"]))

    x = np.arange(len(policies))
    colors = ["#d9534f", "#0275d8", "#5cb85c"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    # Subplot 1: Honest Recovery Rate (Mean ± Std)
    ax1.bar(x, mean_honest, yerr=std_honest, capsize=6, color=colors, alpha=0.85, edgecolor="black", linewidth=1.2)
    ax1.set_ylabel("Mean Honest Recovery Rate (%)", fontsize=11)
    ax1.set_title("Multi-Seed Honest Recovery (Mean +/- Std Dev)", fontsize=12, fontweight="bold")
    ax1.set_xticks(x)
    ax1.set_xticklabels(policies, fontsize=11, fontweight="bold")
    ax1.set_ylim(0, 110)
    ax1.grid(axis="y", linestyle="--", alpha=0.5)

    # Subplot 2: Attacker Net Profit (Mean ± Std)
    ax2.bar(x, mean_profits, yerr=std_profits, capsize=6, color=colors, alpha=0.85, edgecolor="black", linewidth=1.2)
    ax2.set_ylabel("Mean Attacker Net Profit (INR)", fontsize=11)
    ax2.set_title("Multi-Seed Attacker Profit (Mean +/- Std Dev)", fontsize=12, fontweight="bold")
    ax2.set_xticks(x)
    ax2.set_xticklabels(policies, fontsize=11, fontweight="bold")
    ax2.grid(axis="y", linestyle="--", alpha=0.5)

    plt.tight_layout()
    plt.savefig(output_png, dpi=300)
    plt.close()
    return output_png


def plot_blockchain_performance(
    blockchain_summary_csv: str = "results/blockchain_performance_summary.csv",
    output_png: str = "results/graphs/blockchain_performance_scaling.png",
) -> str:
    """Plot Merkle tree construction latency and proof verification scaling."""
    setup_matplotlib_env()
    os.makedirs(os.path.dirname(os.path.abspath(output_png)), exist_ok=True)

    leaves = []
    build_ms = []
    proof_gen_us = []
    proof_ver_us = []
    throughput = []

    with open(blockchain_summary_csv, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            leaves.append(int(r["leaf_count"]))
            build_ms.append(float(r["build_latency_ms"]))
            proof_gen_us.append(float(r["proof_gen_us"]))
            proof_ver_us.append(float(r["proof_verify_us"]))
            throughput.append(float(r["throughput_leaves_per_sec"]))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    # Subplot 1: Tree Construction Latency and Throughput
    ax1.plot(leaves, build_ms, marker="o", color="#d9534f", linewidth=2, label="Build Latency (ms)")
    ax1.set_xlabel("Number of Leaves (Audit Events)", fontsize=11)
    ax1.set_ylabel("Construction Time (ms)", color="#d9534f", fontsize=11)
    ax1.set_title("Merkle Tree Construction Latency vs. Scale", fontsize=12, fontweight="bold")
    ax1.grid(True, linestyle="--", alpha=0.5)

    ax1_twin = ax1.twinx()
    ax1_twin.plot(leaves, throughput, marker="s", color="#0275d8", linestyle="--", linewidth=1.5, label="Throughput (leaves/s)")
    ax1_twin.set_ylabel("Throughput (leaves/sec)", color="#0275d8", fontsize=11)

    # Subplot 2: Proof Generation & Verification Latency
    ax2.plot(leaves, proof_gen_us, marker="^", color="#f0ad4e", linewidth=2, label="Proof Generation (µs)")
    ax2.plot(leaves, proof_ver_us, marker="D", color="#5cb85c", linewidth=2, label="Proof Verification (µs)")
    ax2.set_xlabel("Number of Leaves (Audit Events)", fontsize=11)
    ax2.set_ylabel("Latency (microseconds)", fontsize=11)
    ax2.set_title("Inclusion Proof Generation & Verification", fontsize=12, fontweight="bold")
    ax2.legend(loc="upper left")
    ax2.grid(True, linestyle="--", alpha=0.5)

    plt.tight_layout()
    plt.savefig(output_png, dpi=300)
    plt.close()
    return output_png


def generate_all_graphs(results_dir: str = "results") -> List[str]:
    """Generate all comparison charts."""
    graphs_dir = os.path.join(results_dir, "graphs")
    os.makedirs(graphs_dir, exist_ok=True)
    generated = []

    p1 = os.path.join(results_dir, "initial_experiment.csv")
    if os.path.exists(p1):
        g1 = plot_baseline_comparison(p1, os.path.join(graphs_dir, "baseline_comparison.png"))
        generated.append(g1)

    p2 = os.path.join(results_dir, "denomination_summary.csv")
    if os.path.exists(p2):
        g2 = plot_denomination_granularity(p2, os.path.join(graphs_dir, "denomination_granularity_comparison.png"))
        generated.append(g2)

    p3 = os.path.join(results_dir, "receiver_sweep_summary.csv")
    if os.path.exists(p3):
        g3 = plot_receiver_sweep_comparison(p3, os.path.join(graphs_dir, "receiver_sweep_comparison.png"))
        generated.append(g3)

    p4 = os.path.join(results_dir, "multiseed_summary.csv")
    if os.path.exists(p4):
        g4 = plot_multiseed_distribution(p4, os.path.join(graphs_dir, "multiseed_distribution.png"))
        generated.append(g4)

    p5 = os.path.join(results_dir, "blockchain_performance_summary.csv")
    if os.path.exists(p5):
        g5 = plot_blockchain_performance(p5, os.path.join(graphs_dir, "blockchain_performance_scaling.png"))
        generated.append(g5)

    return generated
