"""Entry point for the Offline Payment Research Simulator."""

import sys
from offline_payment.simulation.runner import run_all_simulations


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print("=" * 80)
    print("HYBRID OFFLINE PAYMENT RESEARCH SIMULATOR")
    print("Payer-Liable Settlement and Blockchain Audit Anchoring")
    print("=" * 80)

    # Run full simulation and experiment suites (including initial experiment)
    run_all_simulations(results_dir="results")


if __name__ == "__main__":
    main()
