"""Integration tests for ambiguous transaction submission, queue recovery, and edge-case faults."""

import os
import sqlite3
import pytest
from web3 import Web3

from offline_payment.blockchain.adapter import SimulatedEVMAdapter
from offline_payment.blockchain.anchor_service import (
    AnchorQueueManager,
    AnchorTask,
    AnchorTaskStatus,
)
from offline_payment.blockchain.local_node_adapter import EthereumLocalNodeAdapter


@pytest.fixture
def real_adapter():
    try:
        adapter = EthereumLocalNodeAdapter()
        return adapter
    except Exception as e:
        pytest.skip(f"Local Hardhat EVM node not accessible: {e}")


def test_ambiguous_submission_failure_and_onchain_reconciliation(real_adapter, tmp_path):
    """Test Case 1: Ambiguous transaction submission failure.

    Scenario:
    1. A transaction is submitted to the Hardhat node and successfully mined on-chain.
    2. The client RPC connection drops / times out before the client records the transaction hash
       (simulated by setting task status to SUBMITTED or FAILED_RETRYABLE with last_error without receipt).
    3. The application restarts (reloading queue from SQLite).
    4. Upon reprocessing, the QueueManager must perform on-chain state reconciliation via getAnchor().
    5. The QueueManager detects that the batch is already anchored on-chain with the matching Merkle root.
    6. It marks the task ANCHORED without re-submitting (no duplicate transaction revert).
    7. The original on-chain anchor record is fully preserved.
    """
    db_file = str(tmp_path / "ambiguous_test.db")
    qm1 = AnchorQueueManager(adapter=real_adapter, db_path=db_file)

    batch_id = f"batch_ambig_{real_adapter.w3.eth.block_number}"
    merkle_root = "0x" + "a9" * 32
    metadata_hash = "0x" + "00" * 32

    # Step 1: Submit directly to chain so it is mined, but simulate client dropped connection before saving receipt
    tx_hash = real_adapter.anchor_root(batch_id=batch_id, merkle_root=merkle_root).tx_hash

    # Step 2: Enqueue task in SQLite as if client submitted it and crashed mid-flight
    task = qm1.enqueue_batch(batch_id=batch_id, merkle_root=merkle_root, metadata_hash=metadata_hash)
    task.status = AnchorTaskStatus.SUBMITTED
    task.last_error = "RPC connection dropped before receipt was received"
    qm1._save_task_to_db(task)

    # Step 3: Simulate process crash and restart by creating new QueueManager instance from db_file
    qm2 = AnchorQueueManager(adapter=real_adapter, db_path=db_file)
    recovered_task = qm2.get_task(batch_id)
    assert recovered_task is not None
    assert recovered_task.status == AnchorTaskStatus.SUBMITTED

    # Step 4: Reprocess task. QueueManager must reconcile with on-chain state via get_anchor
    start_block = real_adapter.w3.eth.block_number
    processed_task = qm2.process_task(recovered_task)

    # Step 5: Verify task is ANCHORED and on-chain record matches without submitting a new transaction
    assert processed_task.status == AnchorTaskStatus.ANCHORED
    assert processed_task.receipt is not None
    assert processed_task.receipt.merkle_root == merkle_root.removeprefix("0x").lower()
    assert real_adapter.w3.eth.block_number == start_block  # No extra transaction was mined!


def test_rpc_timeout_before_submission(real_adapter, tmp_path):
    """Test Case 2: RPC timeout before submission (transient network failure).

    The task should transition to FAILED_RETRYABLE with retry_count incremented.
    """
    db_file = str(tmp_path / "timeout_before.db")
    sim = SimulatedEVMAdapter()
    sim.network_down = True  # Network down before call

    qm = AnchorQueueManager(adapter=sim, default_max_retries=3, db_path=db_file)
    task = qm.enqueue_batch("batch_to_before", "11" * 32)
    assert task.status == AnchorTaskStatus.QUEUED

    qm.process_task(task)
    assert task.status == AnchorTaskStatus.FAILED_RETRYABLE
    assert task.retry_count == 1
    assert "unreachable" in task.last_error.lower()

    # Recovery upon reconnection
    sim.network_down = False
    qm.process_task(task)
    assert task.status == AnchorTaskStatus.ANCHORED
    assert task.retry_count == 1


def test_rpc_timeout_after_submission_retry_reconciliation(real_adapter, tmp_path):
    """Test Case 3: Reconcile duplicate batch error when previous timeout transaction was actually mined."""
    db_file = str(tmp_path / "timeout_after.db")
    qm = AnchorQueueManager(adapter=real_adapter, db_path=db_file)

    batch_id = f"batch_timeout_after_{real_adapter.w3.eth.block_number}"
    merkle_root = "22" * 32

    # Enqueue task
    task = qm.enqueue_batch(batch_id, merkle_root)
    # Mine on-chain behind the scenes
    real_adapter.anchor_root(batch_id, merkle_root)

    # Now let QueueManager process the task.
    # It must check on-chain state, recognize the batch is already anchored, and mark ANCHORED cleanly
    qm.process_task(task)
    assert task.status == AnchorTaskStatus.ANCHORED
    assert task.last_error is None


def test_process_restart_with_pending_tasks(tmp_path):
    """Test Case 4: Process restart with multiple uncommitted and pending tasks."""
    db_file = str(tmp_path / "restart_pending.db")
    sim = SimulatedEVMAdapter()

    qm1 = AnchorQueueManager(adapter=sim, db_path=db_file)
    t1 = qm1.enqueue_batch("b_pending_1", "33" * 32)
    t2 = qm1.enqueue_batch("b_pending_2", "44" * 32)
    qm1.process_task(t1)  # t1 anchored, t2 still queued

    # Simulate crash and restart
    qm2 = AnchorQueueManager(adapter=sim, db_path=db_file)
    assert qm2.get_task("b_pending_1").status == AnchorTaskStatus.ANCHORED
    assert qm2.get_task("b_pending_2").status == AnchorTaskStatus.QUEUED
    assert "b_pending_2" in qm2.queue

    qm2.process_all_pending()
    assert qm2.get_task("b_pending_2").status == AnchorTaskStatus.ANCHORED


def test_duplicate_and_conflicting_queue_requests(tmp_path):
    """Test Case 5: Idempotency with identical payloads vs explicit error with conflicting payloads."""
    db_file = str(tmp_path / "idem_conflict.db")
    sim = SimulatedEVMAdapter()
    qm = AnchorQueueManager(adapter=sim, db_path=db_file)

    batch_id = "batch_idempotent_test"
    root_a = "aa" * 32
    root_b = "bb" * 32

    # First request
    t1 = qm.enqueue_batch(batch_id, root_a, metadata_hash="00" * 32)
    # Identical request returns same task object
    t2 = qm.enqueue_batch(batch_id, root_a, metadata_hash="00" * 32)
    assert t1.task_id == t2.task_id

    # Conflicting root must raise ValueError
    with pytest.raises(ValueError) as exc1:
        qm.enqueue_batch(batch_id, root_b, metadata_hash="00" * 32)
    assert "ConflictingBatchRegistration" in str(exc1.value)

    # Conflicting metadata must raise ValueError
    with pytest.raises(ValueError) as exc2:
        qm.enqueue_batch(batch_id, root_a, metadata_hash="ff" * 32)
    assert "ConflictingBatchRegistration" in str(exc2.value)
def test_queue_conflict_recovery_onchain_mismatch(real_adapter, tmp_path):
    """Test on-chain conflict recovery:
    - A batch ID already exists on-chain with root R1.
    - An anchor task is enqueued with the same batch ID but a conflicting root R2.
    - The queue manager restarts from SQLite and attempts to process the task.
    - Expected result: explicit conflict/error state (FAILED_FINAL), never ANCHORED.
    """
    db_file = str(tmp_path / "conflict_recovery.db")
    qm1 = AnchorQueueManager(adapter=real_adapter, db_path=db_file)

    batch_id = f"batch_conflict_onchain_{real_adapter.w3.eth.block_number}"
    root_onchain = "aa" * 32
    root_conflicting = "bb" * 32

    # Step 1: Anchor root_onchain directly on the real node
    real_adapter.anchor_root(batch_id, root_onchain)

    # Step 2: Enqueue task into queue manager with conflicting root_conflicting
    task = qm1.enqueue_batch(batch_id, root_conflicting)
    assert task.status == AnchorTaskStatus.QUEUED

    # Step 3: Simulate restart
    qm2 = AnchorQueueManager(adapter=real_adapter, db_path=db_file)
    recovered_task = qm2.get_task(batch_id)
    assert recovered_task is not None

    # Step 4: Process task in restarted manager
    processed_task = qm2.process_task(recovered_task)

    # Step 5: Verify task is in explicit conflict error state (FAILED_FINAL), NOT ANCHORED
    assert processed_task.status == AnchorTaskStatus.FAILED_FINAL
    assert "OnChainConflictingMerkleRoot" in processed_task.last_error
    assert root_onchain.lower() in processed_task.last_error
    assert root_conflicting.lower() in processed_task.last_error
def test_queue_conflict_recovery_metadata_mismatch(real_adapter, tmp_path):
    """Test on-chain metadata hash conflict recovery:
    - A batch ID already exists on-chain with root R and metadata hash M1.
    - An anchor task is enqueued with the same batch ID, same root R, but different metadata hash M2.
    - The queue manager restarts from SQLite and attempts to process the task.
    - Expected result: explicit conflict/error state (FAILED_FINAL), never ANCHORED.
    """
    db_file = str(tmp_path / "metadata_conflict_recovery.db")
    qm1 = AnchorQueueManager(adapter=real_adapter, db_path=db_file)

    batch_id = f"batch_meta_conflict_{real_adapter.w3.eth.block_number}"
    root = "cc" * 32
    meta_onchain = "11" * 32
    meta_conflicting = "22" * 32

    # Step 1: Anchor batch with meta_onchain directly on the real node
    real_adapter.anchor_root(batch_id, root, metadata_hash=meta_onchain)

    # Step 2: Enqueue task with same batch_id, same root, but conflicting metadata hash
    task = qm1.enqueue_batch(batch_id, root, metadata_hash=meta_conflicting)
    assert task.status == AnchorTaskStatus.QUEUED

    # Step 3: Simulate restart from SQLite
    qm2 = AnchorQueueManager(adapter=real_adapter, db_path=db_file)
    recovered_task = qm2.get_task(batch_id)
    assert recovered_task is not None

    # Step 4: Process task in restarted manager
    processed_task = qm2.process_task(recovered_task)

    # Step 5: Verify task is in explicit conflict error state (FAILED_FINAL), NOT ANCHORED
    assert processed_task.status == AnchorTaskStatus.FAILED_FINAL
    assert "OnChainConflictingMetadataHash" in processed_task.last_error
    assert meta_onchain.lower() in processed_task.last_error
    assert meta_conflicting.lower() in processed_task.last_error
