"""
EXP-07 Identity-Mapping Integrity Tests
========================================
Verifies that the sequence CSV correctly records claim identity across all
ordering strategies after the fix that removed the erroneous positional lookup
  orig_c = base_scenario.claims[ingestion_pos - 1]
and replaced it with the identity-preserving form
  "original_tx_uuid": c.tx_uuid

Test IDs: IM-01 through IM-07 (seven distinct invariants).
"""

from __future__ import annotations

import csv
import os
import tempfile
from collections import defaultdict

import pytest

from offline_payment.experiments.adversarial_evaluation import AdversarialEvaluationSuite


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def identity_suite():
    """Return (suite, tmpdir) for identity-mapping tests.

    Uses a small but representative parameter set:
    - batch_sizes: [10, 50]
    - seed_count: 3
    so the full run is fast but covers both mule and honest claims plus
    all five ordering strategies.
    """
    tmpdir = tempfile.mkdtemp(prefix="test_exp07_identity_")
    suite = AdversarialEvaluationSuite(output_dir=tmpdir)
    runs, summary, sequences, cross_regime = suite.run_experiment_07_macro_ordering_strategies(
        batch_sizes=[10, 50],
        seed_count=3,
        output_subdir="test_identity",
    )
    return runs, summary, sequences, cross_regime, tmpdir


# ---------------------------------------------------------------------------
# IM-01  tx_uuid == original_tx_uuid for every row in every strategy
# ---------------------------------------------------------------------------

def test_im01_original_tx_uuid_equals_tx_uuid_for_all_strategies(identity_suite):
    """IM-01: tx_uuid must equal original_tx_uuid in every sequence row."""
    _runs, _summary, sequences, _cross, _tmpdir = identity_suite
    assert sequences, "sequence dataset must not be empty"
    failures = [
        f"strategy={r['ordering_strategy']} N={r['batch_size']} seed={r['seed']} "
        f"pos={r['ingestion_position']}: tx_uuid={r['tx_uuid']!r} != "
        f"original_tx_uuid={r['original_tx_uuid']!r}"
        for r in sequences
        if r["tx_uuid"] != r["original_tx_uuid"]
    ]
    assert not failures, (
        f"{len(failures)} rows violate tx_uuid == original_tx_uuid:\n"
        + "\n".join(failures[:20])
    )


# ---------------------------------------------------------------------------
# IM-02  original_ingestion_position is within 1..N for each population
# ---------------------------------------------------------------------------

def test_im02_original_positions_within_range(identity_suite):
    """IM-02: original_ingestion_position ∈ [1, N] for every row."""
    _runs, _summary, sequences, _cross, _tmpdir = identity_suite
    failures = []
    for r in sequences:
        N = int(r["batch_size"])
        opos = int(r["original_ingestion_position"])
        if not (1 <= opos <= N):
            failures.append(
                f"strategy={r['ordering_strategy']} N={N} seed={r['seed']}: "
                f"original_ingestion_position={opos} out of [1,{N}]"
            )
    assert not failures, "\n".join(failures[:20])


# ---------------------------------------------------------------------------
# IM-03  original_ingestion_position values are unique within each population
# ---------------------------------------------------------------------------

def test_im03_original_positions_unique_within_population(identity_suite):
    """IM-03: original positions are a permutation of 1..N within each (N, strategy, seed)."""
    _runs, _summary, sequences, _cross, _tmpdir = identity_suite
    grouped: dict = defaultdict(list)
    for r in sequences:
        key = (int(r["batch_size"]), r["ordering_strategy"], int(r["seed"]))
        grouped[key].append(int(r["original_ingestion_position"]))

    failures = []
    for (N, strat, seed), positions in grouped.items():
        if sorted(positions) != list(range(1, N + 1)):
            failures.append(
                f"strategy={strat} N={N} seed={seed}: "
                f"original positions {sorted(positions)} != {list(range(1, N+1))}"
            )
    assert not failures, "\n".join(failures[:10])


# ---------------------------------------------------------------------------
# IM-04  ingestion_position values are exactly 1..N within each (N, strategy, seed)
# ---------------------------------------------------------------------------

def test_im04_ingestion_positions_complete_and_sequential(identity_suite):
    """IM-04: ingestion_position covers 1..N exactly once per (N, strategy, seed)."""
    _runs, _summary, sequences, _cross, _tmpdir = identity_suite
    grouped: dict = defaultdict(list)
    for r in sequences:
        key = (int(r["batch_size"]), r["ordering_strategy"], int(r["seed"]))
        grouped[key].append(int(r["ingestion_position"]))

    failures = []
    for (N, strat, seed), positions in grouped.items():
        if sorted(positions) != list(range(1, N + 1)):
            failures.append(
                f"strategy={strat} N={N} seed={seed}: "
                f"ingestion positions are not exactly 1..{N}"
            )
    assert not failures, "\n".join(failures[:10])


# ---------------------------------------------------------------------------
# IM-05  Sorting by original_ingestion_position reconstructs GENUINE_FIFO order
# ---------------------------------------------------------------------------

def test_im05_reconstruct_genuine_fifo_from_original_positions(identity_suite):
    """IM-05: For each (N, seed), sorting any strategy by original_ingestion_position
    reproduces the GENUINE_FIFO tx_uuid order.
    """
    _runs, _summary, sequences, _cross, _tmpdir = identity_suite

    # Build GENUINE_FIFO reference: (N, seed) -> [tx_uuid in ingestion order]
    fifo_ref: dict = {}
    for r in sequences:
        if r["ordering_strategy"] == "GENUINE_FIFO":
            key = (int(r["batch_size"]), int(r["seed"]))
            fifo_ref.setdefault(key, []).append(r)
    for key in fifo_ref:
        fifo_ref[key] = [
            row["tx_uuid"]
            for row in sorted(fifo_ref[key], key=lambda x: int(x["ingestion_position"]))
        ]

    # For every other deterministic strategy, reconstruct via original positions
    failures = []
    for strat in ("MULE_FIRST", "HONEST_FIRST", "INTERLEAVED_FIFO"):
        for r_key, fifo_uuids in fifo_ref.items():
            N, seed = r_key
            rows = [
                row for row in sequences
                if row["ordering_strategy"] == strat
                and int(row["batch_size"]) == N
                and int(row["seed"]) == seed
            ]
            reconstructed = [
                row["tx_uuid"]
                for row in sorted(rows, key=lambda x: int(x["original_ingestion_position"]))
            ]
            if reconstructed != fifo_uuids:
                failures.append(
                    f"strategy={strat} N={N} seed={seed}: "
                    f"reconstructed FIFO order does not match reference"
                )
    assert not failures, "\n".join(failures[:10])


# ---------------------------------------------------------------------------
# IM-06  GENUINE_FIFO ingestion_position == original_ingestion_position
# ---------------------------------------------------------------------------

def test_im06_genuine_fifo_positions_are_self_consistent(identity_suite):
    """IM-06: In GENUINE_FIFO, ingestion_position must equal original_ingestion_position."""
    _runs, _summary, sequences, _cross, _tmpdir = identity_suite
    failures = [
        f"N={r['batch_size']} seed={r['seed']} uuid={r['tx_uuid']}: "
        f"ingestion={r['ingestion_position']} != original={r['original_ingestion_position']}"
        for r in sequences
        if r["ordering_strategy"] == "GENUINE_FIFO"
        and int(r["ingestion_position"]) != int(r["original_ingestion_position"])
    ]
    assert not failures, (
        f"{len(failures)} GENUINE_FIFO rows where ingestion_position != original_ingestion_position:\n"
        + "\n".join(failures[:20])
    )


# ---------------------------------------------------------------------------
# IM-07  Reordered strategies have >= 1 row where positions differ (non-trivial)
# ---------------------------------------------------------------------------

def test_im07_reordered_strategies_have_displaced_claims(identity_suite):
    """IM-07: At least one row in each reordered strategy (N=50) has
    ingestion_position != original_ingestion_position, confirming genuine reordering.
    """
    _runs, _summary, sequences, _cross, _tmpdir = identity_suite
    for strat in ("MULE_FIRST", "HONEST_FIRST", "INTERLEAVED_FIFO"):
        displaced = [
            r for r in sequences
            if r["ordering_strategy"] == strat
            and int(r["batch_size"]) == 50
            and int(r["ingestion_position"]) != int(r["original_ingestion_position"])
        ]
        assert displaced, (
            f"Strategy {strat} N=50: no claim was displaced "
            f"(ingestion_position == original_ingestion_position for all rows) — "
            f"reordering may be a no-op."
        )
