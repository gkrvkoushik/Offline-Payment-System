"""Publication-quality visualization module for adversarial settlement evaluation.

Generates:
1. order_sensitivity_recovery.png: Honest recovery against claim order permutations
2. order_sensitivity_profit.png: Attacker net profit against claim order permutations
3. reserve_ratio_recovery.png: Honest recovery against reserve ratio (rho) with 95% CI bands
4. mule_concentration_profit.png: Attacker profit against mule concentration with 95% CI
5. claim_size_comparison.png: Policy comparison across claim-size heterogeneity configurations
"""

import csv
import os
from typing import Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def setup_matplotlib_env(cache_dir: str = "results/.mpl_cache") -> None:
    """Ensure matplotlib cache directory is writable."""
    os.makedirs(cache_dir, exist_ok=True)
    os.environ["MPLCONFIGDIR"] = os.path.abspath(cache_dir)


POLICY_COLORS = {
    "FIRST_CLAIM": "#d9534f",      # Crimson red
    "GLOBAL_PRO_RATA": "#0275d8",   # Steel blue
    "PAYER_LIABILITY": "#5cb85c",  # Forest green
    "FC": "#d9534f",
    "PR": "#0275d8",
    "PL": "#5cb85c",
}

POLICY_LABELS = {
    "FIRST_CLAIM": "First Claim Wins (FC)",
    "GLOBAL_PRO_RATA": "Global Pro-Rata (PR)",
    "PAYER_LIABILITY": "Payer-Liable Strict Prefix (PL)",
    "FC": "FC",
    "PR": "PR",
    "PL": "PL",
}


def plot_order_sensitivity_recovery(
    runs_csv: str = "results/adversarial_evaluation/order_sensitivity_runs.csv",
    output_png: str = "results/adversarial_evaluation/plots/order_sensitivity_recovery.png",
) -> str:
    """Plot honest recovery rate against all 6 claim ingestion order permutations."""
    setup_matplotlib_env()
    os.makedirs(os.path.dirname(output_png), exist_ok=True)

    rows = []
    with open(runs_csv, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    # Subplots: Left = Distinct Permits (Case B), Right = Shared Permit / Double Spend (Case A)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5), sharey=True)

    for ax, c_type, title in [
        (ax1, "distinct_permits", "Case B: Distinct Permits (Pure Reserve Competition)"),
        (ax2, "same_permit", "Case A: Shared Permit (Double-Spending Conflict)"),
    ]:
        subset = [r for r in rows if r["permit_conflict_type"] == c_type]
        order_names = sorted(list(set(r["order_sequence"] for r in subset)))
        x = np.arange(len(order_names))
        width = 0.26

        policies = ["FIRST_CLAIM", "GLOBAL_PRO_RATA", "PAYER_LIABILITY"]
        for p_idx, pol in enumerate(policies):
            vals = []
            for ord_name in order_names:
                matches = [
                    float(r["honest_recovery_rate"]) * 100.0
                    for r in subset
                    if r["order_sequence"] == ord_name and r["policy"] == pol and r["honest_recovery_rate"] != "N/A"
                ]
                vals.append(matches[0] if matches else 0.0)

            ax.bar(
                x + (p_idx - 1) * width,
                vals,
                width,
                label=POLICY_LABELS[pol],
                color=POLICY_COLORS[pol],
                alpha=0.85,
                edgecolor="black",
                linewidth=0.8,
            )

        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.set_xlabel("Claim Ingestion Order", fontsize=11)
        ax.set_xticks(x)
        ax.set_xticklabels(order_names, rotation=35, ha="right", fontsize=9)
        ax.grid(axis="y", linestyle="--", alpha=0.5)

    ax1.set_ylabel("Honest Merchant Recovery Rate (%)", fontsize=11, fontweight="bold")
    ax1.legend(loc="upper right", framealpha=0.9)
    plt.tight_layout()
    plt.savefig(output_png, dpi=300)
    plt.close()
    return output_png


def plot_order_sensitivity_profit(
    runs_csv: str = "results/adversarial_evaluation/order_sensitivity_runs.csv",
    output_png: str = "results/adversarial_evaluation/plots/order_sensitivity_profit.png",
) -> str:
    """Plot attacker net profit against all 6 claim ingestion order permutations."""
    setup_matplotlib_env()
    os.makedirs(os.path.dirname(output_png), exist_ok=True)

    rows = []
    with open(runs_csv, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5), sharey=True)

    for ax, c_type, title in [
        (ax1, "distinct_permits", "Case B: Distinct Permits (Pure Reserve Competition)"),
        (ax2, "same_permit", "Case A: Shared Permit (Double-Spending Conflict)"),
    ]:
        subset = [r for r in rows if r["permit_conflict_type"] == c_type]
        order_names = sorted(list(set(r["order_sequence"] for r in subset)))
        x = np.arange(len(order_names))
        width = 0.26

        policies = ["FIRST_CLAIM", "GLOBAL_PRO_RATA", "PAYER_LIABILITY"]
        for p_idx, pol in enumerate(policies):
            vals = []
            for ord_name in order_names:
                matches = [
                    float(r["attacker_net_profit_paise"]) / 100.0  # to INR
                    for r in subset
                    if r["order_sequence"] == ord_name and r["policy"] == pol
                ]
                vals.append(matches[0] if matches else 0.0)

            ax.bar(
                x + (p_idx - 1) * width,
                vals,
                width,
                label=POLICY_LABELS[pol],
                color=POLICY_COLORS[pol],
                alpha=0.85,
                edgecolor="black",
                linewidth=0.8,
            )

        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.set_xlabel("Claim Ingestion Order", fontsize=11)
        ax.set_xticks(x)
        ax.set_xticklabels(order_names, rotation=35, ha="right", fontsize=9)
        ax.grid(axis="y", linestyle="--", alpha=0.5)

    ax1.set_ylabel("Attacker Net Profit (INR)", fontsize=11, fontweight="bold")
    ax1.legend(loc="upper right", framealpha=0.9)
    plt.tight_layout()
    plt.savefig(output_png, dpi=300)
    plt.close()
    return output_png


def plot_reserve_ratio_recovery(
    summary_csv: str = "results/adversarial_evaluation/reserve_ratio_summary.csv",
    output_png: str = "results/adversarial_evaluation/plots/reserve_ratio_recovery.png",
) -> str:
    """Plot honest recovery against reserve ratio rho with 95% confidence intervals."""
    setup_matplotlib_env()
    os.makedirs(os.path.dirname(output_png), exist_ok=True)

    rows = []
    with open(summary_csv, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))

    policies = ["FIRST_CLAIM", "GLOBAL_PRO_RATA", "PAYER_LIABILITY"]
    ratios = sorted(list(set(float(r["reserve_ratio"]) for r in rows)))

    markers = {"FIRST_CLAIM": "o", "GLOBAL_PRO_RATA": "s", "PAYER_LIABILITY": "^"}

    for pol in policies:
        sub = [r for r in rows if r["policy"] == pol]
        sub.sort(key=lambda x: float(x["reserve_ratio"]))

        x_vals = [float(r["reserve_ratio"]) for r in sub]
        y_rec = [float(r["mean_honest_recovery"]) * 100.0 for r in sub]
        ci_low = [float(r["ci95_low_honest_recovery"]) * 100.0 for r in sub]
        ci_high = [float(r["ci95_high_honest_recovery"]) * 100.0 for r in sub]

        y_profit = [float(r["mean_attacker_profit_paise"]) / 100.0 for r in sub]
        p_ci_low = [float(r["ci95_low_attacker_profit_paise"]) / 100.0 for r in sub]
        p_ci_high = [float(r["ci95_high_attacker_profit_paise"]) / 100.0 for r in sub]

        # Plot Recovery
        ax1.plot(
            x_vals,
            y_rec,
            marker=markers[pol],
            linewidth=2.4,
            label=POLICY_LABELS[pol],
            color=POLICY_COLORS[pol],
        )
        ax1.fill_between(x_vals, ci_low, ci_high, color=POLICY_COLORS[pol], alpha=0.15)

        # Plot Attacker Profit
        ax2.plot(
            x_vals,
            y_profit,
            marker=markers[pol],
            linewidth=2.4,
            label=POLICY_LABELS[pol],
            color=POLICY_COLORS[pol],
        )
        ax2.fill_between(x_vals, p_ci_low, p_ci_high, color=POLICY_COLORS[pol], alpha=0.15)

    ax1.set_title("Honest Recovery Rate vs Reserve Ratio (rho = S/X)", fontsize=12, fontweight="bold")
    ax1.set_xlabel("Reserve Ratio (rho = S/X)", fontsize=11)
    ax1.set_ylabel("Honest Recovery Rate (%)", fontsize=11, fontweight="bold")
    ax1.set_xticks(ratios)
    ax1.grid(True, linestyle="--", alpha=0.5)
    ax1.legend(loc="lower right", framealpha=0.9)

    ax2.set_title("Attacker Net Profit vs Reserve Ratio (rho = S/X)", fontsize=12, fontweight="bold")
    ax2.set_xlabel("Reserve Ratio (rho = S/X)", fontsize=11)
    ax2.set_ylabel("Attacker Net Profit (INR)", fontsize=11, fontweight="bold")
    ax2.set_xticks(ratios)
    ax2.grid(True, linestyle="--", alpha=0.5)
    ax2.legend(loc="upper right", framealpha=0.9)

    plt.tight_layout()
    plt.savefig(output_png, dpi=300)
    plt.close()
    return output_png


def plot_mule_concentration_profit(
    summary_csv: str = "results/adversarial_evaluation/mule_concentration_summary.csv",
    output_png: str = "results/adversarial_evaluation/plots/mule_concentration_profit.png",
) -> str:
    """Plot attacker profit against mule concentration with single vs multi-mule topologies."""
    setup_matplotlib_env()
    os.makedirs(os.path.dirname(output_png), exist_ok=True)

    rows = []
    with open(summary_csv, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5), sharey=True)

    policies = ["FIRST_CLAIM", "GLOBAL_PRO_RATA", "PAYER_LIABILITY"]
    markers = {"FIRST_CLAIM": "o", "GLOBAL_PRO_RATA": "s", "PAYER_LIABILITY": "^"}

    for ax, topo, title in [
        (ax1, "single_mule", "Single Attacker-Controlled Account"),
        (ax2, "multi_mule", "Multiple Attacker-Controlled Accounts (Distributed)"),
    ]:
        for pol in policies:
            # Note: For share=0, topo might be 'no_mule', so include share=0
            sub = [
                r for r in rows
                if r["policy"] == pol and (r["mule_topology"] == topo or float(r["mule_share_pct"]) == 0.0)
            ]
            sub.sort(key=lambda x: float(x["mule_share_pct"]))

            x_vals = [float(r["mule_share_pct"]) for r in sub]
            y_profit = [float(r["mean_attacker_profit_paise"]) / 100.0 for r in sub]
            p_ci_low = [float(r["ci95_low_attacker_profit_paise"]) / 100.0 for r in sub]
            p_ci_high = [float(r["ci95_high_attacker_profit_paise"]) / 100.0 for r in sub]

            ax.plot(
                x_vals,
                y_profit,
                marker=markers[pol],
                linewidth=2.4,
                label=POLICY_LABELS[pol],
                color=POLICY_COLORS[pol],
            )
            ax.fill_between(x_vals, p_ci_low, p_ci_high, color=POLICY_COLORS[pol], alpha=0.15)

        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.set_xlabel("Mule Claim Share (%)", fontsize=11)
        ax.set_xticks([0, 10, 25, 50, 75, 100])
        ax.grid(True, linestyle="--", alpha=0.5)

    ax1.set_ylabel("Attacker Net Profit (INR)", fontsize=11, fontweight="bold")
    ax1.legend(loc="upper left", framealpha=0.9)
    plt.tight_layout()
    plt.savefig(output_png, dpi=300)
    plt.close()
    return output_png


def plot_claim_size_comparison(
    summary_csv: str = "results/adversarial_evaluation/claim_size_summary.csv",
    output_png: str = "results/adversarial_evaluation/plots/claim_size_comparison.png",
) -> str:
    """Plot policy comparison across claim-size heterogeneity configurations with error bars."""
    setup_matplotlib_env()
    os.makedirs(os.path.dirname(output_png), exist_ok=True)

    rows = []
    with open(summary_csv, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

    configs = [
        "Equal_Claims",
        "Small_Mule_Claim",
        "Large_Mule_Claim",
        "Unequal_Honest_Claims",
        "Multiple_Mule_Claims",
    ]
    display_names = [
        "Equal Claims\n(500,500,500)",
        "Small Mule\n(200,650,650)",
        "Large Mule\n(800,350,350)",
        "Unequal Honest\n(500,200,800)",
        "Multi Mule\n(250,250,500,500)",
    ]

    x = np.arange(len(configs))
    width = 0.26
    policies = ["FIRST_CLAIM", "GLOBAL_PRO_RATA", "PAYER_LIABILITY"]

    for p_idx, pol in enumerate(policies):
        rec_means = []
        rec_errs = []
        profit_means = []
        profit_errs = []

        for cfg in configs:
            sub = [r for r in rows if r["configuration_name"] == cfg and r["policy"] == pol]
            if sub:
                mean_r = float(sub[0]["mean_honest_recovery"]) * 100.0
                std_r = float(sub[0]["std_honest_recovery"]) * 100.0 if sub[0]["std_honest_recovery"] != "N/A" else 0.0
                mean_p = float(sub[0]["mean_attacker_profit_paise"]) / 100.0
                std_p = float(sub[0]["std_attacker_profit_paise"]) / 100.0 if sub[0]["std_attacker_profit_paise"] != "N/A" else 0.0
            else:
                mean_r, std_r, mean_p, std_p = 0.0, 0.0, 0.0, 0.0

            rec_means.append(mean_r)
            rec_errs.append(std_r)
            profit_means.append(mean_p)
            profit_errs.append(std_p)

        # Plot recovery
        ax1.bar(
            x + (p_idx - 1) * width,
            rec_means,
            width,
            yerr=rec_errs,
            capsize=4,
            label=POLICY_LABELS[pol],
            color=POLICY_COLORS[pol],
            alpha=0.85,
            edgecolor="black",
            linewidth=0.8,
        )

        # Plot profit
        ax2.bar(
            x + (p_idx - 1) * width,
            profit_means,
            width,
            yerr=profit_errs,
            capsize=4,
            label=POLICY_LABELS[pol],
            color=POLICY_COLORS[pol],
            alpha=0.85,
            edgecolor="black",
            linewidth=0.8,
        )

    ax1.set_title("Honest Recovery Rate Across Heterogeneous Claim Sizes", fontsize=12, fontweight="bold")
    ax1.set_ylabel("Honest Recovery Rate (%)", fontsize=11, fontweight="bold")
    ax1.set_xticks(x)
    ax1.set_xticklabels(display_names, fontsize=9)
    ax1.grid(axis="y", linestyle="--", alpha=0.5)
    ax1.legend(loc="upper right", framealpha=0.9)

    ax2.set_title("Attacker Net Profit Across Heterogeneous Claim Sizes", fontsize=12, fontweight="bold")
    ax2.set_ylabel("Attacker Net Profit (INR)", fontsize=11, fontweight="bold")
    ax2.set_xticks(x)
    ax2.set_xticklabels(display_names, fontsize=9)
    ax2.grid(axis="y", linestyle="--", alpha=0.5)
    ax2.legend(loc="upper right", framealpha=0.9)

    plt.tight_layout()
    plt.savefig(output_png, dpi=300)
    plt.close()
    return output_png


def generate_all_adversarial_plots(eval_dir: str = "results/adversarial_evaluation") -> List[str]:
    """Generate all 5 publication-quality comparison plots."""
    plots_dir = os.path.join(eval_dir, "plots")
    os.makedirs(plots_dir, exist_ok=True)

    generated = []
    generated.append(plot_order_sensitivity_recovery(
        runs_csv=os.path.join(eval_dir, "order_sensitivity_runs.csv"),
        output_png=os.path.join(plots_dir, "order_sensitivity_recovery.png"),
    ))
    generated.append(plot_order_sensitivity_profit(
        runs_csv=os.path.join(eval_dir, "order_sensitivity_runs.csv"),
        output_png=os.path.join(plots_dir, "order_sensitivity_profit.png"),
    ))
    generated.append(plot_reserve_ratio_recovery(
        summary_csv=os.path.join(eval_dir, "reserve_ratio_summary.csv"),
        output_png=os.path.join(plots_dir, "reserve_ratio_recovery.png"),
    ))
    generated.append(plot_mule_concentration_profit(
        summary_csv=os.path.join(eval_dir, "mule_concentration_summary.csv"),
        output_png=os.path.join(plots_dir, "mule_concentration_profit.png"),
    ))
    generated.append(plot_claim_size_comparison(
        summary_csv=os.path.join(eval_dir, "claim_size_summary.csv"),
        output_png=os.path.join(plots_dir, "claim_size_comparison.png"),
    ))
    return generated
