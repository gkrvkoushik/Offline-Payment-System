"""Independent reproducibility verification and reconciliation script for all adversarial evaluation experiments.

Regenerates:
- Common-eligibility comparison
- Shared-permit conflict comparison
- Reserve-ratio sensitivity
- Mule concentration
- Claim-size heterogeneity
- Account-splitting experiment
- Small-mule exhaustive six-permutation analysis

Compares regenerated files against published files and writes experiment_reconciliation.csv.
"""

import csv
import os
import shutil
import time
from typing import Any, Dict, List, Optional

from offline_payment.experiments.adversarial_evaluation import AdversarialEvaluationSuite


REPRO_DIR = "results/reproduced_adversarial_evaluation"
PUB_DIR = "results/adversarial_evaluation"
DEFAULT_TOLERANCE = 1e-4


def compare_csv_files(
    pub_path: str,
    repro_path: str,
    tolerance: float = DEFAULT_TOLERANCE,
) -> Dict[str, Any]:
    """Compare published and reproduced CSV files row-by-row and cell-by-cell.

    Requirements enforced:
    1. Validate every row has exactly the same number of columns as its header.
    2. Compare every cell without zip() truncation that could silently ignore missing cells.
    3. Literal string equality is strictly required for EXACT_MATCH.
    4. If differences exist only in floating-point numbers within tolerance, report MATCH_WITHIN_TOLERANCE.
    5. Include tolerance and mismatch details in output dictionary.
    """
    if not os.path.exists(pub_path):
        return {
            "status": "FAIL_PUB_MISSING",
            "pub_rows": 0,
            "repro_rows": 0,
            "col_count": 0,
            "tolerance": tolerance,
            "tolerance_matches_count": 0,
            "mismatches": ["Published file missing"],
        }
    if not os.path.exists(repro_path):
        return {
            "status": "FAIL_REPRO_MISSING",
            "pub_rows": 0,
            "repro_rows": 0,
            "col_count": 0,
            "tolerance": tolerance,
            "tolerance_matches_count": 0,
            "mismatches": ["Reproduced file missing"],
        }

    with open(pub_path, mode="r", encoding="utf-8") as f:
        pub_reader = list(csv.reader(f))
    with open(repro_path, mode="r", encoding="utf-8") as f:
        repro_reader = list(csv.reader(f))

    if not pub_reader and not repro_reader:
        return {
            "status": "EXACT_MATCH",
            "pub_rows": 0,
            "repro_rows": 0,
            "col_count": 0,
            "tolerance": tolerance,
            "tolerance_matches_count": 0,
            "mismatches": [],
        }

    pub_header = pub_reader[0] if pub_reader else []
    repro_header = repro_reader[0] if repro_reader else []

    if pub_header != repro_header:
        return {
            "status": "HEADER_MISMATCH",
            "pub_rows": max(0, len(pub_reader) - 1),
            "repro_rows": max(0, len(repro_reader) - 1),
            "col_count": len(pub_header),
            "tolerance": tolerance,
            "tolerance_matches_count": 0,
            "mismatches": [f"Headers differ: published={pub_header} vs reproduced={repro_header}"],
        }

    col_count = len(pub_header)

    # 1. Validate every row has exactly the same number of columns as its header
    for r_idx, row in enumerate(pub_reader[1:], start=1):
        if len(row) != col_count:
            return {
                "status": "ROW_COLUMN_COUNT_MISMATCH",
                "pub_rows": len(pub_reader) - 1,
                "repro_rows": len(repro_reader) - 1,
                "col_count": col_count,
                "tolerance": tolerance,
                "tolerance_matches_count": 0,
                "mismatches": [f"Published row {r_idx} has {len(row)} columns, expected {col_count}"],
            }

    for r_idx, row in enumerate(repro_reader[1:], start=1):
        if len(row) != col_count:
            return {
                "status": "ROW_COLUMN_COUNT_MISMATCH",
                "pub_rows": len(pub_reader) - 1,
                "repro_rows": len(repro_reader) - 1,
                "col_count": col_count,
                "tolerance": tolerance,
                "tolerance_matches_count": 0,
                "mismatches": [f"Reproduced row {r_idx} has {len(row)} columns, expected {col_count}"],
            }

    pub_data = pub_reader[1:]
    repro_data = repro_reader[1:]

    # 2. Validate total row count matches
    if len(pub_data) != len(repro_data):
        return {
            "status": "ROW_COUNT_MISMATCH",
            "pub_rows": len(pub_data),
            "repro_rows": len(repro_data),
            "col_count": col_count,
            "tolerance": tolerance,
            "tolerance_matches_count": 0,
            "mismatches": [f"Row count differs: published={len(pub_data)} vs reproduced={len(repro_data)}"],
        }

    # 3. Cell-by-cell comparison across all rows and columns
    mismatches: List[str] = []
    tolerance_matches: List[str] = []

    for r_idx in range(len(pub_data)):
        p_row = pub_data[r_idx]
        r_row = repro_data[r_idx]

        for c_idx in range(col_count):
            p_val = p_row[c_idx]
            r_val = r_row[c_idx]
            col_name = pub_header[c_idx]

            # Literal string equality check
            if p_val == r_val:
                continue

            # Check if difference is a float within tolerance
            try:
                p_f = float(p_val)
                r_f = float(r_val)
                diff = abs(p_f - r_f)
                if diff <= tolerance:
                    tolerance_matches.append(
                        f"Row {r_idx+1} Col '{col_name}': pub={p_val} repro={r_val} (diff={diff:.2e} <= tol={tolerance})"
                    )
                else:
                    mismatches.append(
                        f"Row {r_idx+1} Col '{col_name}': pub={p_val} repro={r_val} (diff={diff:.2e} > tol={tolerance})"
                    )
            except ValueError:
                # String or non-numeric difference is a hard mismatch
                mismatches.append(f"Row {r_idx+1} Col '{col_name}': pub='{p_val}' repro='{r_val}'")

    if mismatches:
        status = "VALUE_MISMATCH"
    elif tolerance_matches:
        status = "MATCH_WITHIN_TOLERANCE"
    else:
        status = "EXACT_MATCH"

    return {
        "status": status,
        "pub_rows": len(pub_data),
        "repro_rows": len(repro_data),
        "col_count": col_count,
        "tolerance": tolerance,
        "tolerance_matches_count": len(tolerance_matches),
        "mismatches": mismatches,
    }


def main():
    print("=" * 80)
    print("INDEPENDENT REPRODUCIBILITY AUDIT: EXPERIMENT REGENERATION & RECONCILIATION")
    print("=" * 80)

    if os.path.exists(REPRO_DIR):
        shutil.rmtree(REPRO_DIR)
    os.makedirs(REPRO_DIR, exist_ok=True)

    t0 = time.time()
    suite = AdversarialEvaluationSuite(output_dir=REPRO_DIR)

    # 1. Common Eligibility
    print("Reproducing Task 2: Common-Eligibility Comparison...")
    suite.run_common_eligibility_comparison()

    # 2. Shared Permit
    print("Reproducing Task 3: Shared-Permit Conflict Comparison...")
    suite.run_shared_permit_conflict_comparison()

    # 3. Reserve Ratio
    print("Reproducing Experiment B: Reserve-Ratio Sensitivity...")
    suite.run_experiment_b_reserve_ratio(seed_count=100)

    # 4. Mule Concentration
    print("Reproducing Experiment C: Mule Concentration...")
    suite.run_experiment_c_mule_concentration(seed_count=100)

    # 5. Claim Size Heterogeneity + Small Mule Analytical
    print("Reproducing Experiment D: Claim-Size Heterogeneity & Small Mule Analytical...")
    suite.run_reconciled_experiment_d(seed_count=100)

    # 6. Account Splitting
    print("Reproducing Task 5: Account-Splitting Invariance...")
    suite.run_account_splitting_experiment(k_values=[1, 2, 5, 10])

    # 7. EXP-07: Macro Claim-Ordering Strategies
    print("Reproducing EXP-07: Macro Claim-Ordering Strategies...")
    suite.run_experiment_07_macro_ordering_strategies(
        batch_sizes=[10, 50, 100], seed_count=30, output_subdir="exp07_ordering_strategies"
    )

    # 8. EXP-08: Funding-Source Sensitivity
    print("Reproducing EXP-08: Funding-Source Composition Sensitivity...")
    suite.run_experiment_08_funding_source_sensitivity(output_subdir="exp08_funding_sensitivity")

    t1 = time.time()
    print(f"Reproduction completed in {t1 - t0:.2f} seconds.")

    # Target CSVs to reconcile
    files_to_compare = [
        "common_eligibility_runs.csv",
        "common_eligibility_summary.csv",
        "shared_permit_runs.csv",
        "shared_permit_summary.csv",
        "reserve_ratio_runs.csv",
        "reserve_ratio_summary.csv",
        "mule_concentration_runs.csv",
        "mule_concentration_summary.csv",
        "claim_size_runs.csv",
        "claim_size_summary.csv",
        "small_mule_analytical_reconciliation.csv",
        "account_splitting_runs.csv",
        "account_splitting_summary.csv",
        os.path.join("exp07_ordering_strategies", "ordering_strategies_runs.csv"),
        os.path.join("exp07_ordering_strategies", "ordering_strategies_summary.csv"),
        os.path.join("exp07_ordering_strategies", "ordering_strategies_order_sequences.csv"),
        os.path.join("exp07_ordering_strategies", "ordering_strategies_cross_regime_sensitivity.csv"),
        os.path.join("exp08_funding_sensitivity", "funding_source_runs.csv"),
        os.path.join("exp08_funding_sensitivity", "funding_source_summary.csv"),
        os.path.join("exp08_funding_sensitivity", "funding_source_reconciliation.csv"),
    ]

    reconciliation_rows = []
    print("\n" + "=" * 80)
    print("RECONCILIATION SUMMARY AGAINST PUBLISHED DATA (LITERAL EQUALITY AUDIT)")
    print("=" * 80)

    for fname in files_to_compare:
        pub_p = os.path.join(PUB_DIR, fname)
        rep_p = os.path.join(REPRO_DIR, fname)
        res = compare_csv_files(pub_p, rep_p, tolerance=DEFAULT_TOLERANCE)

        print(
            f"  {fname:<42} | Status: {res['status']:<22} | Rows: {res['repro_rows']:<5} | TolMatches: {res['tolerance_matches_count']}"
        )

        reconciliation_rows.append({
            "csv_filename": fname,
            "status": res["status"],
            "published_rows": res["pub_rows"],
            "reproduced_rows": res["repro_rows"],
            "columns_count": res["col_count"],
            "tolerance_used": str(res["tolerance"]),
            "tolerance_matches_count": res["tolerance_matches_count"],
            "mismatch_count": len(res["mismatches"]),
            "sample_mismatch": "; ".join(res["mismatches"][:3]) if res["mismatches"] else "None",
        })

    # Write experiment_reconciliation.csv in workspace root
    out_csv = "experiment_reconciliation.csv"
    with open(out_csv, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "csv_filename",
                "status",
                "published_rows",
                "reproduced_rows",
                "columns_count",
                "tolerance_used",
                "tolerance_matches_count",
                "mismatch_count",
                "sample_mismatch",
            ],
        )
        writer.writeheader()
        writer.writerows(reconciliation_rows)

    print(f"\nReconciliation report written to {out_csv}.")


if __name__ == "__main__":
    main()
