#!/usr/bin/env python3
"""
Generate research-paper figures and tables from the frozen experiment CSVs.

Run from the project root:
    uv run python scripts/generate_paper_results.py

Optional:
    uv run python scripts/generate_paper_results.py --project-root . \
        --output-dir research_paper_artifacts

This script DOES NOT rerun simulations or modify source experiment results.
It reads results/*.csv and writes publication-oriented outputs into a separate
folder (default: research_paper_artifacts/).
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
from pathlib import Path
from typing import Iterable

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


POLICY_ORDER = ["FIRST_CLAIM", "GLOBAL_PRO_RATA", "PAYER_LIABILITY"]
POLICY_CANONICAL = {
    "FIRST_CLAIM": "FIRST_CLAIM", "FC": "FIRST_CLAIM",
    "GLOBAL_PRO_RATA": "GLOBAL_PRO_RATA", "PR": "GLOBAL_PRO_RATA",
    "PAYER_LIABILITY": "PAYER_LIABILITY", "PL": "PAYER_LIABILITY",
}


def canonical_policy(value: str) -> str:
    return POLICY_CANONICAL.get(value, value)


def policy_rows(rows: list[dict[str, str]], policy: str) -> list[dict[str, str]]:
    return [r for r in rows if canonical_policy(r.get("policy", "")) == policy]
POLICY_LABELS = {
    "FIRST_CLAIM": "First Claim Wins (FC)",
    "GLOBAL_PRO_RATA": "Global Pro-Rata (PR)",
    "PAYER_LIABILITY": "Payer-Liable Strict Prefix (PL)",
    "FC": "FC",
    "PR": "PR",
    "PL": "PL",
}
POLICY_SHORT = {
    "FIRST_CLAIM": "FC",
    "GLOBAL_PRO_RATA": "PR",
    "PAYER_LIABILITY": "PL",
    "FC": "FC",
    "PR": "PR",
    "PL": "PL",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        print(f"[SKIP] Missing: {path}")
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    fields = fieldnames or list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def num(row: dict, key: str, default=float("nan")) -> float:
    try:
        value = row.get(key, "")
        if value in ("", None, "N/A", "NA", "None"):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def label_policy(value: str) -> str:
    return POLICY_LABELS.get(value, value)


def policy_sort(rows: list[dict[str, str]], key: str = "policy") -> list[dict[str, str]]:
    rank = {p: i for i, p in enumerate(POLICY_ORDER)}
    return sorted(rows, key=lambda r: (rank.get(canonical_policy(r.get(key, "")), 99), r.get(key, "")))


def save_figure(fig, out_dir: Path, stem: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / f"{stem}.png", dpi=400, bbox_inches="tight")
    fig.savefig(out_dir / f"{stem}.pdf", bbox_inches="tight")
    fig.savefig(out_dir / f"{stem}.svg", bbox_inches="tight")
    plt.close(fig)
    print(f"[FIG] {stem}")


def setup_axes(ax, ylabel: str, xlabel: str = "") -> None:
    ax.set_ylabel(ylabel)
    if xlabel:
        ax.set_xlabel(xlabel)
    ax.grid(True, axis="y", linestyle="--", alpha=0.35)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def grouped_bar(ax, rows, category_key, value_key, group_key="policy",
                category_order=None, ylabel="", value_scale=1.0):
    categories = category_order or sorted({r[category_key] for r in rows})
    groups = [p for p in POLICY_ORDER if any(canonical_policy(r.get(group_key, "")) == p for r in rows)]
    if not groups:
        groups = sorted({r.get(group_key, "") for r in rows})
    x = np.arange(len(categories))
    width = 0.8 / max(len(groups), 1)
    for i, group in enumerate(groups):
        vals = []
        for category in categories:
            match = next((r for r in rows
                          if r.get(category_key) == category and canonical_policy(r.get(group_key, "")) == group), None)
            vals.append(num(match, value_key) * value_scale if match else np.nan)
        ax.bar(x + (i - (len(groups) - 1) / 2) * width, vals, width,
               label=label_policy(group))
    ax.set_xticks(x)
    ax.set_xticklabels(categories, rotation=25, ha="right")
    setup_axes(ax, ylabel, category_key.replace("_", " ").title())
    ax.legend()


def plot_initial(root: Path, figs: Path) -> None:
    rows = policy_sort(read_csv(root / "results/initial_experiment.csv"))
    if not rows:
        return
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    x = np.arange(len(rows))
    labels = [POLICY_SHORT.get(r.get("policy", ""), r.get("policy", "")) for r in rows]
    axes[0].bar(x, [num(r, "honest_recovery_rate") * 100 for r in rows])
    axes[0].set_xticks(x, labels)
    setup_axes(axes[0], "Honest merchant recovery (%)", "Settlement policy")
    axes[1].bar(x, [num(r, "attacker_profit_inr") for r in rows])
    axes[1].set_xticks(x, labels)
    setup_axes(axes[1], "Attacker net profit (INR)", "Settlement policy")
    fig.suptitle("Baseline settlement-policy comparison")
    fig.tight_layout()
    save_figure(fig, figs, "fig01_baseline_policy_comparison")


def plot_multiseed(root: Path, figs: Path) -> None:
    rows = policy_sort(read_csv(root / "results/multiseed_summary.csv"))
    if not rows:
        return
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    x = np.arange(len(rows))
    labels = [POLICY_SHORT.get(r["policy"], r["policy"]) for r in rows]
    means = np.array([num(r, "mean_honest_recovery_rate") * 100 for r in rows])
    stds = np.array([num(r, "std_honest_recovery_rate") * 100 for r in rows])
    axes[0].bar(x, means, yerr=stds, capsize=4)
    axes[0].set_xticks(x, labels)
    setup_axes(axes[0], "Honest merchant recovery (%)", "Settlement policy")
    pmean = np.array([num(r, "mean_attacker_profit_inr") for r in rows])
    pstd = np.array([num(r, "std_attacker_profit_inr") for r in rows])
    axes[1].bar(x, pmean, yerr=pstd, capsize=4)
    axes[1].set_xticks(x, labels)
    setup_axes(axes[1], "Attacker net profit (INR)", "Settlement policy")
    fig.suptitle("Multi-seed policy evaluation (mean ± standard deviation)")
    fig.tight_layout()
    save_figure(fig, figs, "fig02_multiseed_policy_comparison")


def plot_receiver_sweep(root: Path, figs: Path) -> None:
    rows = read_csv(root / "results/receiver_sweep_summary.csv")
    if not rows:
        return
    # The mule_position dimension is retained; create one figure per position.
    positions = sorted({r.get("mule_position", "") for r in rows})
    for pos in positions:
        subset = [r for r in rows if r.get("mule_position") == pos]
        fig, ax = plt.subplots(figsize=(7.2, 4.8))
        for policy in POLICY_ORDER:
            group = sorted(policy_rows(subset, policy),
                           key=lambda r: num(r, "num_receivers"))
            if not group:
                continue
            ax.plot([num(r, "num_receivers") for r in group],
                    [num(r, "honest_recovery_rate") * 100 for r in group],
                    marker="o", linewidth=2, label=label_policy(policy))
        setup_axes(ax, "Honest merchant recovery (%)", "Number of receivers")
        ax.set_title(f"Receiver scaling — mule position: {pos}")
        ax.legend()
        fig.tight_layout()
        save_figure(fig, figs, f"fig03_receiver_scaling_{pos.lower()}")


def plot_reserve_coverage(root: Path, figs: Path) -> None:
    rows = read_csv(root / "results/reserve_coverage_summary.csv")
    if not rows:
        return
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.3))
    for policy in POLICY_ORDER:
        group = sorted(policy_rows(rows, policy),
                       key=lambda r: num(r, "coverage_ratio"))
        if not group:
            continue
        x = [num(r, "coverage_ratio") for r in group]
        y = [num(r, "honest_recovery_rate") * 100 for r in group]
        axes[0].plot(x, y, marker="o", label=label_policy(policy))
        axes[1].plot(x, [num(r, "attacker_profit_inr") for r in group],
                     marker="o", label=label_policy(policy))
    setup_axes(axes[0], "Honest merchant recovery (%)", "Reserve coverage ratio")
    setup_axes(axes[1], "Attacker net profit (INR)", "Reserve coverage ratio")
    axes[0].legend()
    axes[1].legend()
    fig.suptitle("Reserve coverage sensitivity")
    fig.tight_layout()
    save_figure(fig, figs, "fig04_reserve_coverage_sensitivity")


def plot_denomination(root: Path, figs: Path) -> None:
    rows = read_csv(root / "results/denomination_summary.csv")
    if not rows:
        return
    # Use the primary funding configuration when available; retain all denomination types.
    configs = sorted({r.get("funding_config", "") for r in rows})
    chosen = "standard" if "standard" in [c.lower() for c in configs] else configs[0]
    selected = [r for r in rows if r.get("funding_config", "").lower() == chosen.lower()]
    denoms = sorted({r.get("denomination_config", "") for r in selected})
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.3))
    grouped_bar(axes[0], selected, "denomination_config", "honest_recovery_rate",
                category_order=denoms, ylabel="Honest merchant recovery (%)", value_scale=100)
    grouped_bar(axes[1], selected, "denomination_config", "stranded_permit_value_inr",
                category_order=denoms, ylabel="Stranded permit value (INR)")
    fig.suptitle(f"Permit denomination sensitivity — funding: {chosen}")
    fig.tight_layout()
    save_figure(fig, figs, "fig05_permit_denomination_sensitivity")


def plot_order_conflicts(root: Path, figs: Path) -> None:
    common = read_csv(root / "results/adversarial_evaluation/common_eligibility_summary.csv")
    shared = read_csv(root / "results/adversarial_evaluation/shared_permit_summary.csv")
    if not common and not shared:
        return
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.4), sharey=True)
    for ax, rows, title in [
        (axes[0], common, "Common eligibility: distinct permits"),
        (axes[1], shared, "Shared-permit conflict"),
    ]:
        rows = policy_sort(rows)
        x = np.arange(len(rows))
        vals = [num(r, "order_sensitivity_recovery") * 100 for r in rows]
        labels = [POLICY_SHORT.get(r.get("policy", ""), r.get("policy", "")) for r in rows]
        ax.bar(x, vals)
        ax.set_xticks(x, labels)
        ax.set_title(title)
        setup_axes(ax, "Order sensitivity (percentage points)", "Settlement policy")
    fig.tight_layout()
    save_figure(fig, figs, "fig06_permit_and_order_conflict_sensitivity")


def plot_reserve_ratio(root: Path, figs: Path) -> None:
    rows = read_csv(root / "results/adversarial_evaluation/reserve_ratio_summary.csv")
    if not rows:
        return
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.4))
    for policy in POLICY_ORDER:
        group = sorted(policy_rows(rows, policy),
                       key=lambda r: num(r, "reserve_ratio"))
        if not group:
            continue
        x = np.array([num(r, "reserve_ratio") for r in group])
        y = np.array([num(r, "mean_honest_recovery") * 100 for r in group])
        lo = np.array([num(r, "ci95_low_honest_recovery") * 100 for r in group])
        hi = np.array([num(r, "ci95_high_honest_recovery") * 100 for r in group])
        axes[0].plot(x, y, marker="o", label=label_policy(policy))
        axes[0].fill_between(x, lo, hi, alpha=0.15)
        py = np.array([num(r, "mean_attacker_profit_paise") / 100 for r in group])
        plo = np.array([num(r, "ci95_low_attacker_profit_paise") / 100 for r in group])
        phi = np.array([num(r, "ci95_high_attacker_profit_paise") / 100 for r in group])
        axes[1].plot(x, py, marker="o", label=label_policy(policy))
        axes[1].fill_between(x, plo, phi, alpha=0.15)
    setup_axes(axes[0], "Honest merchant recovery (%)", "Reserve ratio (S/X)")
    setup_axes(axes[1], "Attacker net profit (INR)", "Reserve ratio (S/X)")
    axes[0].legend()
    axes[1].legend()
    fig.suptitle("Reserve-ratio sensitivity (mean and reported 95% CI)")
    fig.tight_layout()
    save_figure(fig, figs, "fig07_reserve_ratio_sensitivity")


def plot_mule_concentration(root: Path, figs: Path) -> None:
    rows = read_csv(root / "results/adversarial_evaluation/mule_concentration_summary.csv")
    if not rows:
        return
    topologies = sorted({r.get("mule_topology", "") for r in rows})
    for topology in topologies:
        subset = [r for r in rows if r.get("mule_topology") == topology]
        fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.3))
        for policy in POLICY_ORDER:
            group = sorted(policy_rows(subset, policy),
                           key=lambda r: num(r, "mule_share_pct"))
            if not group:
                continue
            x = [num(r, "mule_share_pct") for r in group]
            axes[0].plot(x, [num(r, "mean_honest_recovery") * 100 for r in group],
                         marker="o", label=label_policy(policy))
            axes[1].plot(x, [num(r, "mean_attacker_profit_paise") / 100 for r in group],
                         marker="o", label=label_policy(policy))
        setup_axes(axes[0], "Honest merchant recovery (%)", "Mule claim-value share (%)")
        setup_axes(axes[1], "Attacker net profit (INR)", "Mule claim-value share (%)")
        axes[0].legend()
        axes[1].legend()
        fig.suptitle(f"Mule concentration — topology: {topology}")
        fig.tight_layout()
        save_figure(fig, figs, f"fig08_mule_concentration_{topology.lower()}")


def plot_claim_size(root: Path, figs: Path) -> None:
    rows = read_csv(root / "results/adversarial_evaluation/claim_size_summary.csv")
    if not rows:
        return
    configs = sorted({r.get("configuration_name", "") for r in rows})
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
    for policy in POLICY_ORDER:
        group = policy_rows(rows, policy)
        group.sort(key=lambda r: configs.index(r.get("configuration_name", "")))
        if not group:
            continue
        x = np.arange(len(group))
        y = np.array([num(r, "mean_honest_recovery") * 100 for r in group])
        lo = np.array([num(r, "ci95_low_honest_recovery") * 100 for r in group])
        hi = np.array([num(r, "ci95_high_honest_recovery") * 100 for r in group])
        axes[0].plot(x, y, marker="o", label=label_policy(policy))
        axes[0].errorbar(x, y, yerr=[y - lo, hi - y], fmt="none", capsize=3)
        axes[1].plot(x, [num(r, "mean_attacker_profit_paise") / 100 for r in group],
                     marker="o", label=label_policy(policy))
    axes[0].set_xticks(np.arange(len(configs)), configs, rotation=25, ha="right")
    axes[1].set_xticks(np.arange(len(configs)), configs, rotation=25, ha="right")
    setup_axes(axes[0], "Honest merchant recovery (%)", "Claim-size configuration")
    setup_axes(axes[1], "Attacker net profit (INR)", "Claim-size configuration")
    axes[0].legend()
    axes[1].legend()
    fig.suptitle("Claim-size heterogeneity")
    fig.tight_layout()
    save_figure(fig, figs, "fig09_claim_size_heterogeneity")


def plot_account_splitting(root: Path, figs: Path) -> None:
    rows = read_csv(root / "results/adversarial_evaluation/account_splitting_summary.csv")
    if not rows:
        return
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.3))
    for policy in POLICY_ORDER:
        group = sorted(policy_rows(rows, policy),
                       key=lambda r: num(r, "mule_accounts_k"))
        if not group:
            continue
        x = [num(r, "mule_accounts_k") for r in group]
        axes[0].plot(x, [num(r, "mean_honest_recovery") * 100 for r in group],
                     marker="o", label=label_policy(policy))
        axes[1].plot(x, [num(r, "mean_attacker_profit_paise") / 100 for r in group],
                     marker="o", label=label_policy(policy))
    setup_axes(axes[0], "Honest merchant recovery (%)", "Number of mule accounts (k)")
    setup_axes(axes[1], "Attacker net profit (INR)", "Number of mule accounts (k)")
    axes[0].legend()
    axes[1].legend()
    fig.suptitle("Account-splitting sensitivity")
    fig.tight_layout()
    save_figure(fig, figs, "fig10_account_splitting")


def plot_exp07(root: Path, figs: Path) -> None:
    base = root / "results/adversarial_evaluation/exp07_ordering_strategies"
    rows = read_csv(base / "ordering_strategies_summary.csv")
    sensitivity = read_csv(base / "ordering_strategies_cross_regime_sensitivity.csv")
    if rows:
        strategies = ["GENUINE_FIFO", "INTERLEAVED_FIFO", "RANDOM", "MULE_FIRST", "HONEST_FIRST"]
        fig, axes = plt.subplots(1, 3, figsize=(15, 4.7), sharey=True)
        for ax, policy in zip(axes, POLICY_ORDER):
            subset = policy_rows(rows, policy)
            for strategy in strategies:
                group = sorted([r for r in subset if r.get("ordering_strategy") == strategy],
                               key=lambda r: num(r, "batch_size"))
                if not group:
                    continue
                x = [num(r, "batch_size") for r in group]
                y = [num(r, "mean_honest_recovery") * 100 for r in group]
                ax.plot(x, y, marker="o", label=strategy.replace("_", " ").title())
            ax.set_title(POLICY_SHORT.get(policy, policy))
            setup_axes(ax, "Honest merchant recovery (%)", "Batch size (N)")
        axes[-1].legend(fontsize=8, loc="best")
        fig.suptitle("EXP-07: Ordering strategy and batch size")
        fig.tight_layout()
        save_figure(fig, figs, "fig11_exp07_ordering_strategy_recovery")

    if sensitivity:
        fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.3))
        for ax, key, title, scale, ylabel in [
            (axes[0], "across_regime_os_recovery_rate",
             "Honest recovery sensitivity", 100, "Percentage points"),
            (axes[1], "across_regime_os_profit_paise",
             "Attacker-profit sensitivity", 1 / 100, "INR"),
        ]:
            for policy in POLICY_ORDER:
                group = sorted(policy_rows(sensitivity, policy),
                               key=lambda r: num(r, "batch_size"))
                if not group:
                    continue
                ax.plot([num(r, "batch_size") for r in group],
                        [num(r, key) * scale for r in group],
                        marker="o", label=POLICY_SHORT.get(policy, policy))
            setup_axes(ax, ylabel, "Batch size (N)")
            ax.set_title(title)
            ax.legend()
        fig.suptitle("EXP-07: Across-regime ordering sensitivity")
        fig.tight_layout()
        save_figure(fig, figs, "fig12_exp07_across_regime_sensitivity")


def plot_exp08(root: Path, figs: Path) -> None:
    base = root / "results/adversarial_evaluation/exp08_funding_sensitivity"
    rows = read_csv(base / "funding_source_summary.csv")
    if not rows:
        return
    scenarios = sorted({r.get("attacker_scenario", "") for r in rows})
    for scenario in scenarios:
        subset = [r for r in rows if r.get("attacker_scenario") == scenario]
        # Collapse policy lines separately; use composition label to preserve exact tested mix.
        fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
        for policy in POLICY_ORDER:
            group = sorted(policy_rows(subset, policy),
                           key=lambda r: num(r, "C_paise"))
            if not group:
                continue
            x = np.arange(len(group))
            labels = [r.get("funding_composition", "") for r in group]
            axes[0].plot(x, [num(r, "mean_payer_total_debit_paise") / 100 for r in group],
                         marker="o", label=f"{POLICY_SHORT[policy]} payer debit")
            axes[0].plot(x, [num(r, "mean_issuer_guarantee_expenditure_paise") / 100 for r in group],
                         marker="s", linestyle="--", label=f"{POLICY_SHORT[policy]} issuer")
            axes[1].plot(x, [num(r, "mean_attacker_net_profit_paise") / 100 for r in group],
                         marker="o", label=POLICY_SHORT[policy])
        for ax in axes:
            ax.set_xticks(np.arange(len(group)), labels, rotation=45, ha="right")
        setup_axes(axes[0], "Mean expenditure (INR)", "Funding composition")
        setup_axes(axes[1], "Mean attacker net profit (INR)", "Funding composition")
        axes[0].legend(fontsize=8)
        axes[1].legend()
        fig.suptitle(f"EXP-08: Funding-source sensitivity — {scenario.replace('_', ' ').title()}")
        fig.tight_layout()
        save_figure(fig, figs, f"fig13_exp08_funding_{scenario.lower()}")


def plot_blockchain(root: Path, figs: Path) -> None:
    rows = read_csv(root / "results/blockchain_performance_summary.csv")
    if not rows:
        return
    rows.sort(key=lambda r: num(r, "leaf_count"))
    x = [num(r, "leaf_count") for r in rows]
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.3))
    axes[0].plot(x, [num(r, "build_latency_ms_mean") for r in rows], marker="o", label="Merkle build")
    axes[0].plot(x, [num(r, "anchor_latency_ms_mean") for r in rows], marker="s", label="On-chain anchor")
    axes[0].set_xscale("log", base=2)
    setup_axes(axes[0], "Mean latency (ms)", "Merkle batch size (leaves)")
    axes[0].legend()
    axes[1].plot(x, [num(r, "actual_gas_used") for r in rows], marker="o")
    axes[1].set_xscale("log", base=2)
    setup_axes(axes[1], "Gas used", "Merkle batch size (leaves)")
    fig.suptitle("Blockchain audit-anchoring performance")
    fig.tight_layout()
    save_figure(fig, figs, "fig14_blockchain_audit_performance")


def export_tables(root: Path, tables: Path) -> list[Path]:
    """Copy key source summaries into paper tables and emit LaTeX versions."""
    source_files = [
        "initial_experiment.csv",
        "multiseed_summary.csv",
        "receiver_sweep_summary.csv",
        "reserve_coverage_summary.csv",
        "denomination_summary.csv",
        "blockchain_performance_summary.csv",
        "adversarial_evaluation/common_eligibility_summary.csv",
        "adversarial_evaluation/shared_permit_summary.csv",
        "adversarial_evaluation/reserve_ratio_summary.csv",
        "adversarial_evaluation/mule_concentration_summary.csv",
        "adversarial_evaluation/claim_size_summary.csv",
        "adversarial_evaluation/account_splitting_summary.csv",
        "adversarial_evaluation/exp07_ordering_strategies/ordering_strategies_summary.csv",
        "adversarial_evaluation/exp07_ordering_strategies/ordering_strategies_cross_regime_sensitivity.csv",
        "adversarial_evaluation/exp08_funding_sensitivity/funding_source_summary.csv",
        "adversarial_evaluation/exp08_funding_sensitivity/funding_source_reconciliation.csv",
    ]
    exported = []
    tables.mkdir(parents=True, exist_ok=True)
    for rel in source_files:
        src = root / "results" / rel
        if not src.exists():
            continue
        dest = tables / src.name
        # Avoid collisions by prefixing the parent directory for nested files.
        if dest.exists():
            prefix = src.parent.name + "_"
            dest = tables / f"{prefix}{src.name}"
        shutil.copy2(src, dest)
        exported.append(dest)
        try:
            with src.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.reader(f)
                headers = next(reader)
                data = list(reader)
            tex = tables / f"{dest.stem}.tex"
            with tex.open("w", encoding="utf-8") as f:
                f.write("% Generated from the archived experiment CSV; values are not recalculated.\n")
                f.write("\\begin{tabular}{|" + "l|" * len(headers) + "}\\hline\n")
                f.write(" & ".join(h.replace("_", r"\_") for h in headers) + r" \\ \hline" + "\n")
                for row in data:
                    cells = [str(v).replace("_", r"\_").replace("%", r"\%") for v in row]
                    f.write(" & ".join(cells) + r" \\ \hline" + "\n")
                f.write("\\end{tabular}\n")
        except (StopIteration, UnicodeDecodeError):
            pass
    return exported


def write_readme(out: Path, root: Path, figures: list[str], tables: list[Path]) -> None:
    text = f"""# Research-paper result artifacts

Generated from the frozen experiment CSVs in:
`{(root / 'results').as_posix()}`

This directory is separate from the simulator's source results. The generator
does not rerun simulations, alter settlement logic, or modify the original CSVs.

## Contents

- `figures/`: publication-oriented figures in PNG (400 dpi), PDF and SVG.
- `tables/`: copies of source summary/reconciliation CSVs and LaTeX table files.
- `generation_metadata.json`: input/output inventory.

## Figure inventory

""" + "\n".join(f"- `{name}`" for name in figures) + """

## Interpretation cautions

1. Figures are descriptive visualizations of the archived experiment outputs.
2. Confidence intervals are plotted only where the source summary provides them.
3. EXP-07 deterministic regimes have repeated fixed sequences; zero within-regime
   variation must not be interpreted as evidence of population certainty.
4. EXP-07 genuine FIFO is the project's synthetic mixed-arrival baseline, not an
   empirically observed payment-network arrival distribution.
5. EXP-08 invariance applies only to the fixed claim population, eligibility,
   ordering, policy and reserve configurations tested.
6. Shared-permit conflict results must not be pooled with common-eligibility
   comparisons as though their eligible claim sets were identical.
7. Amounts are converted from paise to INR only for display; archived CSVs remain
   the authoritative numeric source.

Before submitting the paper, verify figure captions, table references, units,
scenario labels and the precise experimental configuration against the paper text.
"""
    (out / "README.md").write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=".", help="Project root containing results/")
    parser.add_argument("--output-dir", default="research_paper_artifacts",
                        help="Separate output folder (relative to project root unless absolute)")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    out = Path(args.output_dir)
    if not out.is_absolute():
        out = (root / out).resolve()
    if not (root / "results").is_dir():
        raise SystemExit(f"Could not find {root / 'results'}. Run from the project root or pass --project-root.")

    figures_dir = out / "figures"
    tables_dir = out / "tables"
    figures_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)

    # Consistent, editable, print-friendly defaults. No source data is modified.
    plt.rcParams.update({
        "figure.dpi": 120,
        "savefig.dpi": 400,
        "font.size": 9,
        "axes.titlesize": 11,
        "axes.labelsize": 9,
        "legend.fontsize": 8,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })

    plotters = [
        plot_initial, plot_multiseed, plot_receiver_sweep, plot_reserve_coverage,
        plot_denomination, plot_order_conflicts, plot_reserve_ratio,
        plot_mule_concentration, plot_claim_size, plot_account_splitting,
        plot_exp07, plot_exp08, plot_blockchain,
    ]
    for plotter in plotters:
        try:
            plotter(root, figures_dir)
        except Exception as exc:
            # Continue so a missing optional dataset does not block other figures.
            print(f"[ERROR] {plotter.__name__}: {exc}")

    exported = export_tables(root, tables_dir)
    figure_names = sorted(p.stem for p in figures_dir.glob("*.png"))
    metadata = {
        "project_root": str(root),
        "input_results_directory": str(root / "results"),
        "output_directory": str(out),
        "figures_png": figure_names,
        "tables_csv": [p.name for p in exported],
        "note": "Generated from existing CSV outputs; simulations were not rerun.",
    }
    (out / "generation_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    write_readme(out, root, figure_names, exported)
    print(f"\nDone. Paper artifacts written to: {out}")
    print(f"Figures: {len(figure_names)}")
    print(f"Source tables copied: {len(exported)}")


if __name__ == "__main__":
    main()
