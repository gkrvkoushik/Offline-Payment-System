"""Executable CLI runner for Adversarial Settlement-Policy Evaluation & Validation.

Executes:
1. Task 2: Common-Eligibility Comparison (Distinct Valid Permits)
2. Task 3: Shared-Permit Conflict Comparison (Explicit Eligibility Breakdown)
3. Experiment B: Reserve Ratio Sensitivity
4. Experiment C: Mule Concentration
5. Experiment D: Reconciled Claim-Size Heterogeneity (Stochastic + Analytical Small Mule)
6. Task 5: Account-Splitting Invariance under Fixed Aggregate Claim Value
7. Manifests & Publication-Quality Visualizations
"""

import os
import sys
import time

from offline_payment.experiments.adversarial_evaluation import AdversarialEvaluationSuite
from offline_payment.visualization.adversarial_plots import generate_all_adversarial_plots


def main():
    print("=" * 80)
    print("TARGETED ADVERSARIAL SETTLEMENT-POLICY VALIDATION & EXTENSION SUITE")
    print("=" * 80)

    t0 = time.time()
    suite = AdversarialEvaluationSuite(output_dir="results/adversarial_evaluation")

    # 1. Task 2: Common-Eligibility Comparison
    comm_runs, comm_sum = suite.run_common_eligibility_comparison()
    print(f"  -> Task 2 (Common Eligibility): {len(comm_runs)} runs, {len(comm_sum)} summary rows")

    # 2. Task 3: Shared-Permit Conflict Comparison
    shared_runs, shared_sum = suite.run_shared_permit_conflict_comparison()
    print(f"  -> Task 3 (Shared Permit): {len(shared_runs)} runs, {len(shared_sum)} summary rows")

    # 3. Experiment B: Reserve Ratio Sensitivity
    b_runs, b_summary = suite.run_experiment_b_reserve_ratio(seed_count=100)
    print(f"  -> Experiment B (Reserve Ratio): {len(b_runs)} runs, {len(b_summary)} summary rows")

    # 4. Experiment C: Mule Concentration
    c_runs, c_summary = suite.run_experiment_c_mule_concentration(seed_count=100)
    print(f"  -> Experiment C (Mule Concentration): {len(c_runs)} runs, {len(c_summary)} summary rows")

    # 5. Experiment D: Reconciled Claim-Size Heterogeneity
    d_runs, d_summary, d_analytical = suite.run_reconciled_experiment_d(seed_count=100)
    print(f"  -> Experiment D (Claim Size): {len(d_runs)} runs, {len(d_summary)} summary rows, {len(d_analytical)} analytical rows")

    # 6. Task 5: Account-Splitting Invariance
    acct_runs, acct_summary = suite.run_account_splitting_experiment(k_values=[1, 2, 5, 10])
    print(f"  -> Task 5 (Account Splitting): {len(acct_runs)} runs, {len(acct_summary)} summary rows")

    # 7. Metadata Manifest
    suite.export_metadata()
    print("  -> Exported experiment_configurations.json and experiment_metadata.json")

    # 8. Visualizations
    plots = generate_all_adversarial_plots(eval_dir="results/adversarial_evaluation")
    print(f"  -> Generated {len(plots)} publication-quality plots in results/adversarial_evaluation/plots/")
    for p in plots:
        print(f"     * {p}")

    total_time = time.time() - t0
    print("=" * 80)
    print(f"VALIDATION & EXTENSION SUITE COMPLETE in {total_time:.2f} seconds.")
    print("=" * 80)


if __name__ == "__main__":
    main()
