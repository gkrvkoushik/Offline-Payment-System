"""Unit tests for BlockchainAdapter, SimulatedEVMAdapter, and AnchorQueueManager."""

import pytest
from offline_payment.blockchain.adapter import SimulatedEVMAdapter, AnchorReceipt
from offline_payment.blockchain.anchor_service import (
    AnchorQueueManager,
    AnchorTaskStatus,
)


def test_simulated_evm_adapter_success():
    adapter = SimulatedEVMAdapter(initial_block=500)
    batch_id = "batch_001"
    root = "a" * 64

    receipt = adapter.anchor_root(batch_id=batch_id, merkle_root=root)

    assert receipt.batch_id == batch_id
    assert receipt.merkle_root == root
    assert receipt.block_number == 501
    assert receipt.gas_used >= 40000
    assert receipt.status == "SUCCESS"
    assert receipt.tx_hash.startswith("0x")

    # Verify retrieval
    stored = adapter.get_anchor(batch_id)
    assert stored is not None
    assert stored.tx_hash == receipt.tx_hash
    assert adapter.verify_anchor_exists(batch_id, root) is True
    assert adapter.verify_anchor_exists(batch_id, "b" * 64) is False


def test_simulated_evm_adapter_rejects_duplicates():
    adapter = SimulatedEVMAdapter()
    batch_id = "batch_dup"
    root = "c" * 64

    adapter.anchor_root(batch_id, root)

    with pytest.raises(ValueError, match="already anchored"):
        adapter.anchor_root(batch_id, root)


def test_simulated_evm_adapter_network_down():
    adapter = SimulatedEVMAdapter()
    adapter.network_down = True

    with pytest.raises(ConnectionError, match="Blockchain RPC unreachable"):
        adapter.anchor_root("batch_net_fail", "d" * 64)


def test_anchor_queue_manager_happy_path():
    adapter = SimulatedEVMAdapter()
    manager = AnchorQueueManager(adapter=adapter)

    task = manager.enqueue_batch(batch_id="batch_q1", merkle_root="1" * 64)
    assert task.status == AnchorTaskStatus.QUEUED
    assert manager.total_pending == 1

    processed = manager.process_queue()
    assert len(processed) == 1
    assert processed[0].status == AnchorTaskStatus.ANCHORED
    assert processed[0].receipt is not None
    assert manager.total_anchored == 1
    assert manager.total_pending == 0


def test_anchor_queue_manager_retry_and_recovery():
    adapter = SimulatedEVMAdapter()
    manager = AnchorQueueManager(adapter=adapter, default_max_retries=3)

    # 1. Enqueue task
    task = manager.enqueue_batch(batch_id="batch_transient", merkle_root="2" * 64)

    # 2. Simulate network outage for 2 calls
    adapter.network_down = True

    manager.process_queue()
    task = manager.get_task("batch_transient")
    assert task.status == AnchorTaskStatus.FAILED_RETRYABLE
    assert task.retry_count == 1
    assert manager.total_pending == 1

    manager.process_queue()
    task = manager.get_task("batch_transient")
    assert task.status == AnchorTaskStatus.FAILED_RETRYABLE
    assert task.retry_count == 2

    # 3. Network recovers
    adapter.network_down = False
    manager.process_queue()
    task = manager.get_task("batch_transient")
    assert task.status == AnchorTaskStatus.ANCHORED
    assert task.receipt is not None
    assert manager.total_anchored == 1


def test_anchor_queue_manager_max_retries_exceeded():
    adapter = SimulatedEVMAdapter()
    manager = AnchorQueueManager(adapter=adapter, default_max_retries=2)

    manager.enqueue_batch(batch_id="batch_fatal", merkle_root="3" * 64)
    adapter.network_down = True

    # Attempt 1: retry_count=1 -> FAILED_RETRYABLE
    manager.process_queue()
    assert manager.get_task("batch_fatal").status == AnchorTaskStatus.FAILED_RETRYABLE

    # Attempt 2: retry_count=2 >= max_retries (2) -> FAILED_FINAL
    manager.process_queue()
    task = manager.get_task("batch_fatal")
    assert task.status == AnchorTaskStatus.FAILED_FINAL
    assert manager.total_failed == 1
    assert manager.total_pending == 0


def test_anchor_queue_manager_idempotency():
    adapter = SimulatedEVMAdapter()
    manager = AnchorQueueManager(adapter=adapter)

    task_1 = manager.enqueue_batch(batch_id="batch_idem", merkle_root="4" * 64)
    manager.process_queue()
    assert task_1.status == AnchorTaskStatus.ANCHORED

    # Re-enqueuing the same batch ID must return the existing anchored task without re-anchoring
    task_2 = manager.enqueue_batch(batch_id="batch_idem", merkle_root="4" * 64)
    assert task_2 is task_1
    assert len(adapter.tx_history) == 1
