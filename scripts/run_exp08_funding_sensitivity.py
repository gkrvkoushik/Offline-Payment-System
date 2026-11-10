"""Standalone CLI Runner for EXP-08: Funding-Source Composition Sensitivity.

Evaluates 11 systematic funding tier compositions (C:H:F) holding total reserve
strictly constant at S = 100,000 paise (INR 1,000) across 3 payer liability
scenarios (malicious_payer, compromised_victim, honest_payer) and all 6 claim
arrival permutations under FC, Global PR, and PL settlement policies.
"""

import os
import sys
import time
from pathlib import Path

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from offline_payment.experiments.adversarial_evaluation import AdversarialEvaluationSuite


def main():
    print("=" * 80)
    print("EXP-08: FUNDING-SOURCE COMPOSITION SENSITIVITY EVALUATION")
    print("=" * 80)

    t0 = time.time()
    suite = AdversarialEvaluationSuite(output_dir="results/adversarial_evaluation")

    runs, summary, reconciliation = suite.run_experiment_08_funding_source_sensitivity(
        output_subdir="exp08_funding_sensitivity"
    )

    elapsed = time.time() - t0
    print(f"\nExecution Complete in {elapsed:.2f}s:")
    print(f"  - Run-level records:      {len(runs)} rows")
    print(f"  - Summary records:        {len(summary)} rows")
    print(f"  - Reconciliation records: {len(reconciliation)} rows")
    print(f"  - Artifact directory:     results/adversarial_evaluation/exp08_funding_sensitivity/")
    print("=" * 80)


if __name__ == "__main__":
    main()
