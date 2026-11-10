"""Standalone CLI Runner for EXP-07: Macro Claim-Ordering Strategies.

Evaluates Genuine FIFO, Interleaved FIFO, Random, Mule-First, and Honest-First
arrival ordering regimes across varying batch sizes (N in [10, 50, 100]) under a
controlled 50% mule-share population and 50% reserve coverage ratio.
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
    print("EXP-07: MACRO CLAIM-ORDERING STRATEGIES EVALUATION")
    print("=" * 80)

    t0 = time.time()
    suite = AdversarialEvaluationSuite(output_dir="results/adversarial_evaluation")

    runs, summary, sequences, cross_regime = suite.run_experiment_07_macro_ordering_strategies(
        batch_sizes=[10, 50, 100],
        seed_count=30,
        output_subdir="exp07_ordering_strategies",
    )

    elapsed = time.time() - t0
    print(f"\nExecution Complete in {elapsed:.2f}s:")
    print(f"  - Run-level records:        {len(runs)} rows")
    print(f"  - Summary records:          {len(summary)} rows")
    print(f"  - Ingestion sequence log:   {len(sequences)} rows")
    print(f"  - Cross-regime sensitivity: {len(cross_regime)} rows")
    print(f"  - Artifact directory:       results/adversarial_evaluation/exp07_ordering_strategies/")
    print("=" * 80)


if __name__ == "__main__":
    main()
