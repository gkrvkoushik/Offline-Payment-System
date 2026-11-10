"""Dedicated test suite for EXP-07: Macro Claim-Ordering Strategies.

Verifies:
1. All five ordering strategies generate valid sequences.
2. Every generated sequence contains every original claim exactly once.
3. No claim value, permit ID, or identity is altered during reordering.
4. Random sequences are reproducible for identical seeds and differ across seeds.
5. Mule-first places all mule claims before honest claims with stable relative category order.
6. Honest-first places all honest claims before mule claims with stable relative category order.
7. Genuine FIFO preserves original deterministic arrival order without rearranging by claimant type.
8. Genuine FIFO is NOT identical to Mule-First for generated populations (compares actual UUIDs and types).
9. Genuine FIFO is NOT identical to Honest-First for generated populations (compares actual UUIDs and types).
10. Interleaved FIFO has intended alternating structure and is distinct from Genuine FIFO.
11. All strategies preserve the exact same claim population, 50% mule share, and 50% reserve coverage.
12. All three settlement policies receive identical ordered claim sequences for each experimental replicate.
13. Output CSVs contain all required fields including original and ordered transaction IDs.
14. Summary statistics separate within-regime variability from across-regime sensitivity.
15. Global Pro-Rata has strictly zero across-regime order sensitivity (OS_across = 0.0).
16. First Claim and Payer Liability exhibit maximal across-regime order sensitivity (OS_across = 1.0).
"""

import csv
import json
import os
import tempfile
import pytest

from offline_payment.config import ClaimType
from offline_payment.experiments.adversarial_evaluation import (
    AdversarialEvaluationSuite,
    compute_sample_stats,
)
from offline_payment.settlement.first_claim import FirstClaimSettlement
from offline_payment.settlement.payer_liability import PayerLiabilitySettlement
from offline_payment.settlement.pro_rata import GlobalProRataSettlement


@pytest.fixture
def temp_suite():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield AdversarialEvaluationSuite(output_dir=tmpdir), tmpdir


def test_exp07_all_strategies_generate_valid_sequences(temp_suite):
    """Test 1 & 2: Generated sequences contain each claim exactly once across all 5 strategies."""
    suite, tmpdir = temp_suite
    runs, summary, sequences, cross_regime = suite.run_experiment_07_macro_ordering_strategies(
        batch_sizes=[10], seed_count=3, output_subdir="test_exp07"
    )

    # For N=10, 5 strategies, 3 seeds = 15 sequences of 10 claims = 150 sequence rows
    assert len(sequences) == 150

    # Group by (seed, strategy)
    grouped = {}
    for row in sequences:
        key = (row["seed"], row["ordering_strategy"])
        grouped.setdefault(key, []).append(row)

    assert len(grouped) == 15

    for (s, strat), rows in grouped.items():
        assert len(rows) == 10
        uuids = [r["tx_uuid"] for r in rows]
        # Exactly once, no duplicates
        assert len(set(uuids)) == 10
        # Positions are 1 to 10
        positions = [r["ingestion_position"] for r in rows]
        assert sorted(positions) == list(range(1, 11))


def test_exp07_no_claim_value_or_identity_altered(temp_suite):
    """Test 3: No claim value, permit ID, or type is altered during reordering."""
    suite, tmpdir = temp_suite
    runs, summary, sequences, cross_regime = suite.run_experiment_07_macro_ordering_strategies(
        batch_sizes=[10], seed_count=2, output_subdir="test_exp07"
    )

    for row in sequences:
        assert row["amount_paise"] == 50000
        assert row["claim_type"] in ("MULE", "HONEST_MERCHANT")
        assert row["permit_id"].startswith("p_exp07_base_N10_")


def test_exp07_random_seed_reproducibility(temp_suite):
    """Test 4: Random sequences are identical for identical seeds and differ across seeds."""
    suite, tmpdir = temp_suite

    runs1, sum1, seq1, cr1 = suite.run_experiment_07_macro_ordering_strategies(
        batch_sizes=[10], seed_count=5, output_subdir="test_exp07_1"
    )
    runs2, sum2, seq2, cr2 = suite.run_experiment_07_macro_ordering_strategies(
        batch_sizes=[10], seed_count=5, output_subdir="test_exp07_2"
    )

    # Exact equality across identical runs
    assert seq1 == seq2

    # Verify that different seeds produce different sequences for Random strategy
    rand_seq_by_seed = {}
    for r in seq1:
        if r["ordering_strategy"] == "RANDOM":
            rand_seq_by_seed.setdefault(r["seed"], []).append(r["tx_uuid"])

    # At least two seeds must have different orders
    orders = [tuple(u_list) for u_list in rand_seq_by_seed.values()]
    assert len(set(orders)) > 1


def test_exp07_mule_first_ordering(temp_suite):
    """Test 5: Mule-First places all mule claims strictly before honest claims with stable category order."""
    suite, tmpdir = temp_suite
    runs, summary, sequences, cross_regime = suite.run_experiment_07_macro_ordering_strategies(
        batch_sizes=[10, 50], seed_count=2, output_subdir="test_exp07"
    )

    for row in sequences:
        if row["ordering_strategy"] == "MULE_FIRST":
            N = row["batch_size"]
            pos = row["ingestion_position"]
            if pos <= N // 2:
                assert row["claim_type"] == "MULE"
            else:
                assert row["claim_type"] == "HONEST_MERCHANT"


def test_exp07_honest_first_ordering(temp_suite):
    """Test 6: Honest-First places all honest claims strictly before mule claims with stable category order."""
    suite, tmpdir = temp_suite
    runs, summary, sequences, cross_regime = suite.run_experiment_07_macro_ordering_strategies(
        batch_sizes=[10, 50], seed_count=2, output_subdir="test_exp07"
    )

    for row in sequences:
        if row["ordering_strategy"] == "HONEST_FIRST":
            N = row["batch_size"]
            pos = row["ingestion_position"]
            if pos <= N // 2:
                assert row["claim_type"] == "HONEST_MERCHANT"
            else:
                assert row["claim_type"] == "MULE"


def test_exp07_genuine_fifo_preserves_original_sequence(temp_suite):
    """Test 7: Genuine FIFO preserves original deterministic arrival order without reordering."""
    suite, tmpdir = temp_suite
    runs, summary, sequences, cross_regime = suite.run_experiment_07_macro_ordering_strategies(
        batch_sizes=[10, 50], seed_count=2, output_subdir="test_exp07"
    )

    # 1. In runs, verify original_claim_sequence == ordered_claim_sequence for GENUINE_FIFO
    for r in runs:
        if r["ordering_strategy"] == "GENUINE_FIFO":
            assert r["original_claim_sequence"] == r["ordered_claim_sequence"]

    # 2. In sequences, verify tx_uuid == original_tx_uuid and ingestion_position == original_ingestion_position
    fifo_rows = [r for r in sequences if r["ordering_strategy"] == "GENUINE_FIFO"]
    for r in fifo_rows:
        assert r["tx_uuid"] == r["original_tx_uuid"]
        assert r["ingestion_position"] == r["original_ingestion_position"]


def test_exp07_genuine_fifo_not_identical_to_mule_first(temp_suite):
    """Test 8: Genuine FIFO is NOT identical to Mule-First (compares actual UUIDs and types)."""
    suite, tmpdir = temp_suite
    runs, summary, sequences, cross_regime = suite.run_experiment_07_macro_ordering_strategies(
        batch_sizes=[10, 50, 100], seed_count=1, output_subdir="test_exp07"
    )

    for N in [10, 50, 100]:
        genuine_seq = [r for r in sequences if r["batch_size"] == N and r["ordering_strategy"] == "GENUINE_FIFO"]
        mule_seq = [r for r in sequences if r["batch_size"] == N and r["ordering_strategy"] == "MULE_FIRST"]

        genuine_uuids = [r["tx_uuid"] for r in genuine_seq]
        mule_uuids = [r["tx_uuid"] for r in mule_seq]

        genuine_types = [r["claim_type"] for r in genuine_seq]
        mule_types = [r["claim_type"] for r in mule_seq]

        # Actual ordered transaction IDs must differ
        assert genuine_uuids != mule_uuids

        # Actual claimant categories must differ
        assert genuine_types != mule_types

        # MULE_FIRST has all mules in the first half
        assert all(t == "MULE" for t in mule_types[:N // 2])

        # GENUINE_FIFO does NOT have all mules in the first half (contains honest claims)
        assert not all(t == "MULE" for t in genuine_types[:N // 2])
        assert any(t == "HONEST_MERCHANT" for t in genuine_types[:N // 2])


def test_exp07_genuine_fifo_not_identical_to_honest_first(temp_suite):
    """Test 9: Genuine FIFO is NOT identical to Honest-First (compares actual UUIDs and types)."""
    suite, tmpdir = temp_suite
    runs, summary, sequences, cross_regime = suite.run_experiment_07_macro_ordering_strategies(
        batch_sizes=[10, 50, 100], seed_count=1, output_subdir="test_exp07"
    )

    for N in [10, 50, 100]:
        genuine_seq = [r for r in sequences if r["batch_size"] == N and r["ordering_strategy"] == "GENUINE_FIFO"]
        honest_seq = [r for r in sequences if r["batch_size"] == N and r["ordering_strategy"] == "HONEST_FIRST"]

        genuine_uuids = [r["tx_uuid"] for r in genuine_seq]
        honest_uuids = [r["tx_uuid"] for r in honest_seq]

        genuine_types = [r["claim_type"] for r in genuine_seq]
        honest_types = [r["claim_type"] for r in honest_seq]

        assert genuine_uuids != honest_uuids
        assert genuine_types != honest_types

        # HONEST_FIRST has all honest in first half
        assert all(t == "HONEST_MERCHANT" for t in honest_types[:N // 2])

        # GENUINE_FIFO does NOT have all honest in first half (contains mule claims)
        assert not all(t == "HONEST_MERCHANT" for t in genuine_types[:N // 2])
        assert any(t == "MULE" for t in genuine_types[:N // 2])


def test_exp07_interleaved_fifo_alternating_structure_and_distinctness(temp_suite):
    """Test 10: Interleaved FIFO alternates arrivals and is distinct from Genuine FIFO."""
    suite, tmpdir = temp_suite
    runs, summary, sequences, cross_regime = suite.run_experiment_07_macro_ordering_strategies(
        batch_sizes=[10, 50], seed_count=1, output_subdir="test_exp07"
    )

    for N in [10, 50]:
        genuine_rows = [r for r in sequences if r["batch_size"] == N and r["ordering_strategy"] == "GENUINE_FIFO"]
        interleaved_rows = [r for r in sequences if r["batch_size"] == N and r["ordering_strategy"] == "INTERLEAVED_FIFO"]

        # Interleaved alternates: pos 1=Mule, pos 2=Honest, pos 3=Mule, pos 4=Honest...
        for r in interleaved_rows:
            pos = r["ingestion_position"]
            if pos % 2 == 1:
                assert r["claim_type"] == "MULE"
            else:
                assert r["claim_type"] == "HONEST_MERCHANT"

        # Distinct sequences from Genuine FIFO
        genuine_uuids = [r["tx_uuid"] for r in genuine_rows]
        interleaved_uuids = [r["tx_uuid"] for r in interleaved_rows]
        assert genuine_uuids != interleaved_uuids

        genuine_types = [r["claim_type"] for r in genuine_rows]
        interleaved_types = [r["claim_type"] for r in interleaved_rows]
        assert genuine_types != interleaved_types


def test_exp07_all_strategies_preserve_exact_same_claim_population(temp_suite):
    """Test 11: All strategies preserve exact claim population, 50% mule share, and 50% coverage."""
    suite, tmpdir = temp_suite
    runs, summary, sequences, cross_regime = suite.run_experiment_07_macro_ordering_strategies(
        batch_sizes=[10, 50], seed_count=2, output_subdir="test_exp07"
    )

    strategies = ["GENUINE_FIFO", "INTERLEAVED_FIFO", "RANDOM", "MULE_FIRST", "HONEST_FIRST"]

    for N in [10, 50]:
        # Reference population from GENUINE_FIFO
        ref_rows = [r for r in sequences if r["batch_size"] == N and r["ordering_strategy"] == "GENUINE_FIFO" and r["seed"] == 1]
        ref_uuids = sorted(r["tx_uuid"] for r in ref_rows)
        assert len(ref_uuids) == N

        for strat in strategies:
            for s in [1, 2]:
                strat_rows = [r for r in sequences if r["batch_size"] == N and r["ordering_strategy"] == strat and r["seed"] == s]
                assert len(strat_rows) == N
                # Multiset of UUIDs is preserved exactly
                assert sorted(r["tx_uuid"] for r in strat_rows) == ref_uuids

                # 50% mule claim share preserved
                mule_count = sum(1 for r in strat_rows if r["claim_type"] == "MULE")
                honest_count = sum(1 for r in strat_rows if r["claim_type"] == "HONEST_MERCHANT")
                assert mule_count == N // 2
                assert honest_count == N // 2

                # Claim values preserved
                total_val = sum(int(r["amount_paise"]) for r in strat_rows)
                assert total_val == N * 50000

        # Check reserve coverage in runs
        for r in runs:
            if r["batch_size"] == N:
                assert r["mule_share"] == 0.50
                assert r["reserve_ratio"] == 0.50
                assert r["total_eligible_paise"] == N * 50000
                assert r["available_reserve_paise"] == (N // 2) * 50000


def test_exp07_identical_ordered_claims_passed_to_all_three_policies(temp_suite):
    """Test 12: All three policies receive identical ordered claim sequences in each replicate."""
    suite, tmpdir = temp_suite
    runs, summary, sequences, cross_regime = suite.run_experiment_07_macro_ordering_strategies(
        batch_sizes=[10], seed_count=2, output_subdir="test_exp07"
    )

    grouped_runs = {}
    for r in runs:
        key = (r["batch_size"], r["ordering_strategy"], r["seed"])
        grouped_runs.setdefault(key, []).append(r)

    for key, pol_runs in grouped_runs.items():
        assert len(pol_runs) == 3
        policies = {r["policy"] for r in pol_runs}
        assert policies == {"FIRST_CLAIM", "GLOBAL_PRO_RATA", "PAYER_LIABILITY"}

        # Identical ordered claim sequence string across all three policies
        ordered_seqs = {r["ordered_claim_sequence"] for r in pol_runs}
        assert len(ordered_seqs) == 1

        # Identical total eligible claim demand
        eligibles = {r["total_eligible_paise"] for r in pol_runs}
        assert len(eligibles) == 1
        assert list(eligibles)[0] == 500000


def test_exp07_csv_files_and_required_columns(temp_suite):
    """Test 13: All CSV files are generated with required headers including original and ordered IDs."""
    suite, tmpdir = temp_suite
    suite.run_experiment_07_macro_ordering_strategies(
        batch_sizes=[10], seed_count=2, output_subdir="test_exp07"
    )

    exp_dir = os.path.join(tmpdir, "test_exp07")
    runs_csv = os.path.join(exp_dir, "ordering_strategies_runs.csv")
    summary_csv = os.path.join(exp_dir, "ordering_strategies_summary.csv")
    seq_csv = os.path.join(exp_dir, "ordering_strategies_order_sequences.csv")
    cfg_json = os.path.join(exp_dir, "ordering_strategies_configuration.json")
    cross_csv = os.path.join(exp_dir, "ordering_strategies_cross_regime_sensitivity.csv")
    rep_md = os.path.join(exp_dir, "ordering_strategies_reproducibility_report.md")

    assert os.path.exists(runs_csv)
    assert os.path.exists(summary_csv)
    assert os.path.exists(seq_csv)
    assert os.path.exists(cfg_json)
    assert os.path.exists(cross_csv)
    assert os.path.exists(rep_md)

    with open(runs_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        for req in [
            "experiment", "batch_size", "ordering_strategy", "seed", "policy",
            "claim_population_id", "original_claim_sequence", "ordered_claim_sequence",
            "mule_share", "reserve_ratio",
            "honest_recovery_rate", "attacker_net_profit_paise", "mule_payout_paise",
            "total_payout_paise", "reserve_utilization", "stranded_reserve_paise"
        ]:
            assert req in fields

    with open(seq_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        for req in [
            "batch_size", "seed", "ordering_strategy", "ingestion_position",
            "tx_uuid", "original_tx_uuid", "original_ingestion_position",
            "claim_type", "amount_paise", "permit_id"
        ]:
            assert req in fields

    with open(summary_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        for req in [
            "experiment", "batch_size", "ordering_strategy", "settlement_policy",
            "regime_type", "is_deterministic",
            "mean_honest_recovery", "std_honest_recovery", "within_regime_os_recovery",
            "mean_attacker_profit_paise", "within_regime_os_profit_paise",
            "variability_interpretation"
        ]:
            assert req in fields

    with open(cross_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        for req in [
            "experiment", "batch_size", "settlement_policy", "evaluated_regimes",
            "min_mean_honest_recovery_rate", "max_mean_honest_recovery_rate",
            "across_regime_os_recovery_rate", "across_regime_os_profit_paise"
        ]:
            assert req in fields


def test_exp07_within_regime_variability_separation(temp_suite):
    """Test 14: Summary statistics properly separate deterministic from stochastic variability."""
    suite, tmpdir = temp_suite
    runs, summary, sequences, cross_regime = suite.run_experiment_07_macro_ordering_strategies(
        batch_sizes=[10], seed_count=5, output_subdir="test_exp07"
    )

    for row in summary:
        strat = row["ordering_strategy"]
        if strat in ("GENUINE_FIFO", "INTERLEAVED_FIFO", "MULE_FIRST", "HONEST_FIRST"):
            assert row["is_deterministic"] is True
            assert row["regime_type"] == "DETERMINISTIC_FIXED_SEQUENCE"
            assert float(row["std_honest_recovery"]) == 0.0
            assert float(row["within_regime_os_recovery"]) == 0.0
            assert "Zero within-regime variability" in row["variability_interpretation"]
        elif strat == "RANDOM":
            assert row["is_deterministic"] is False
            assert row["regime_type"] == "STOCHASTIC_PERMUTATION"
            assert "Stochastic within-regime variability" in row["variability_interpretation"]


def test_exp07_global_pro_rata_across_regime_order_invariance(temp_suite):
    """Test 15: Global Pro-Rata has strictly zero across-regime order sensitivity."""
    suite, tmpdir = temp_suite
    runs, summary, sequences, cross_regime = suite.run_experiment_07_macro_ordering_strategies(
        batch_sizes=[10, 50], seed_count=5, output_subdir="test_exp07"
    )

    for row in cross_regime:
        if row["policy"] == "GLOBAL_PRO_RATA":
            assert pytest.approx(float(row["across_regime_os_recovery_rate"]), abs=1e-6) == 0.00
            assert row["across_regime_os_profit_paise"] == 0
            assert row["across_regime_os_mule_payout_paise"] == 0
            assert row["across_regime_os_total_payout_paise"] == 0


def test_exp07_fc_pl_across_regime_order_sensitivity(temp_suite):
    """Test 16: First Claim and Payer Liability exhibit maximal across-regime order sensitivity."""
    suite, tmpdir = temp_suite
    runs, summary, sequences, cross_regime = suite.run_experiment_07_macro_ordering_strategies(
        batch_sizes=[10, 50], seed_count=5, output_subdir="test_exp07"
    )

    for row in cross_regime:
        if row["policy"] in ("FIRST_CLAIM", "PAYER_LIABILITY"):
            assert float(row["min_mean_honest_recovery_rate"]) == 0.0
            assert float(row["max_mean_honest_recovery_rate"]) == 1.0
            assert pytest.approx(float(row["across_regime_os_recovery_rate"]), abs=1e-6) == 1.00
            assert row["across_regime_os_profit_paise"] > 0
