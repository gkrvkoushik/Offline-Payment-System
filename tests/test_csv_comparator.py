"""Unit tests for the corrected CSV reconciliation comparator.

Tests all deliberate error injections:
1. Exact match (identical files).
2. Small floating-point difference below 1e-4 (MATCH_WITHIN_TOLERANCE).
3. Floating-point difference above 1e-4 (VALUE_MISMATCH).
4. Missing trailing cell in a row (ROW_COLUMN_COUNT_MISMATCH).
5. Extra cell in a row (ROW_COLUMN_COUNT_MISMATCH).
6. Reordered row (VALUE_MISMATCH).
7. Changed header column (HEADER_MISMATCH).
8. Different row count (ROW_COUNT_MISMATCH).
"""

import csv
import os
import sys
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "scripts"))

from reproduce_and_reconcile_experiments import compare_csv_files


@pytest.fixture
def base_csv_data():
    return [
        ["experiment", "policy", "rate", "payout_paise", "notes"],
        ["exp_1", "FIRST_CLAIM", "0.500000", "50000", "ok"],
        ["exp_1", "GLOBAL_PRO_RATA", "0.666667", "66667", "ok"],
        ["exp_1", "PAYER_LIABILITY", "0.500000", "50000", "ok"],
    ]


def write_csv(path: str, data: list):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(data)


def test_comparator_exact_match(tmp_path, base_csv_data):
    pub_file = str(tmp_path / "pub.csv")
    repro_file = str(tmp_path / "repro.csv")
    write_csv(pub_file, base_csv_data)
    write_csv(repro_file, base_csv_data)

    res = compare_csv_files(pub_file, repro_file, tolerance=1e-4)
    assert res["status"] == "EXACT_MATCH"
    assert res["pub_rows"] == 3
    assert res["repro_rows"] == 3
    assert res["col_count"] == 5
    assert res["tolerance_matches_count"] == 0
    assert len(res["mismatches"]) == 0


def test_comparator_small_float_diff_below_tolerance(tmp_path, base_csv_data):
    """Difference of 1e-5 (< 1e-4) must yield MATCH_WITHIN_TOLERANCE."""
    pub_file = str(tmp_path / "pub.csv")
    repro_file = str(tmp_path / "repro.csv")
    write_csv(pub_file, base_csv_data)

    repro_data = [row.copy() for row in base_csv_data]
    # In row 2, change 0.666667 to 0.666677 (diff = 1e-5 < 1e-4)
    repro_data[2][2] = "0.666677"
    write_csv(repro_file, repro_data)

    res = compare_csv_files(pub_file, repro_file, tolerance=1e-4)
    assert res["status"] == "MATCH_WITHIN_TOLERANCE"
    assert res["tolerance_matches_count"] == 1
    assert len(res["mismatches"]) == 0


def test_comparator_float_diff_above_tolerance(tmp_path, base_csv_data):
    """Difference of 5e-4 (> 1e-4) must yield VALUE_MISMATCH."""
    pub_file = str(tmp_path / "pub.csv")
    repro_file = str(tmp_path / "repro.csv")
    write_csv(pub_file, base_csv_data)

    repro_data = [row.copy() for row in base_csv_data]
    # In row 2, change 0.666667 to 0.667167 (diff = 5e-4 > 1e-4)
    repro_data[2][2] = "0.667167"
    write_csv(repro_file, repro_data)

    res = compare_csv_files(pub_file, repro_file, tolerance=1e-4)
    assert res["status"] == "VALUE_MISMATCH"
    assert len(res["mismatches"]) == 1
    assert "diff=5.00e-04 > tol=0.0001" in res["mismatches"][0]


def test_comparator_missing_trailing_cell(tmp_path, base_csv_data):
    """A row missing its trailing cell must fail with ROW_COLUMN_COUNT_MISMATCH."""
    pub_file = str(tmp_path / "pub.csv")
    repro_file = str(tmp_path / "repro.csv")
    write_csv(pub_file, base_csv_data)

    repro_data = [row.copy() for row in base_csv_data]
    # Drop trailing cell from row 1
    repro_data[1] = repro_data[1][:-1]  # 4 cells instead of 5
    write_csv(repro_file, repro_data)

    res = compare_csv_files(pub_file, repro_file, tolerance=1e-4)
    assert res["status"] == "ROW_COLUMN_COUNT_MISMATCH"
    assert "Reproduced row 1 has 4 columns, expected 5" in res["mismatches"][0]


def test_comparator_extra_cell(tmp_path, base_csv_data):
    """A row with an extra cell must fail with ROW_COLUMN_COUNT_MISMATCH."""
    pub_file = str(tmp_path / "pub.csv")
    repro_file = str(tmp_path / "repro.csv")
    write_csv(pub_file, base_csv_data)

    repro_data = [row.copy() for row in base_csv_data]
    # Add extra cell to row 2
    repro_data[2].append("extra_value")
    write_csv(repro_file, repro_data)

    res = compare_csv_files(pub_file, repro_file, tolerance=1e-4)
    assert res["status"] == "ROW_COLUMN_COUNT_MISMATCH"
    assert "Reproduced row 2 has 6 columns, expected 5" in res["mismatches"][0]


def test_comparator_reordered_row(tmp_path, base_csv_data):
    """Swapping two rows must be detected as VALUE_MISMATCH."""
    pub_file = str(tmp_path / "pub.csv")
    repro_file = str(tmp_path / "repro.csv")
    write_csv(pub_file, base_csv_data)

    repro_data = [base_csv_data[0], base_csv_data[2], base_csv_data[1], base_csv_data[3]]
    write_csv(repro_file, repro_data)

    res = compare_csv_files(pub_file, repro_file, tolerance=1e-4)
    assert res["status"] == "VALUE_MISMATCH"
    assert len(res["mismatches"]) > 0


def test_comparator_changed_header(tmp_path, base_csv_data):
    """Changed header column name must fail with HEADER_MISMATCH."""
    pub_file = str(tmp_path / "pub.csv")
    repro_file = str(tmp_path / "repro.csv")
    write_csv(pub_file, base_csv_data)

    repro_data = [row.copy() for row in base_csv_data]
    repro_data[0][4] = "different_header"
    write_csv(repro_file, repro_data)

    res = compare_csv_files(pub_file, repro_file, tolerance=1e-4)
    assert res["status"] == "HEADER_MISMATCH"
    assert "Headers differ" in res["mismatches"][0]
