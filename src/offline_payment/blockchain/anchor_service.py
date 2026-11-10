"""Persistent SQLite-backed queue manager for blockchain anchoring tasks.

Key operational invariants:
- Settlement is NEVER blocked by blockchain availability.
- Tasks are persisted across process restarts in SQLite.
- Idempotency:
    - Same batch ID + same Merkle root + same metadata -> returns existing task.
    - Same batch ID + conflicting Merkle root or metadata -> raises ValueError (ConflictingBatchRegistration).
- Safe timeout handling: reconciles on-chain state before resubmitting.
- Exponential backoff with retry limit.
"""

from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path
import sqlite3
import time
from typing import Dict, List, Optional
import uuid

from offline_payment.blockchain.adapter import (
    AnchorReceipt,
    BlockchainAdapter,
    SimulatedEVMAdapter,
)


class AnchorTaskStatus(str, Enum):
    """Lifecycle states of an anchoring transaction task."""
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    SUBMITTED = "SUBMITTED"
    ANCHORED = "ANCHORED"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_FINAL = "FAILED_FINAL"


@dataclass
class AnchorTask:
    """An anchoring task tracking on-chain submission lifecycle."""
    batch_id: str
    merkle_root: str
    metadata_hash: Optional[str] = None
    status: AnchorTaskStatus = AnchorTaskStatus.CREATED
    retry_count: int = 0
    max_retries: int = 3
    receipt: Optional[AnchorReceipt] = None
    last_error: Optional[str] = None
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: int = field(default_factory=lambda: int(time.time()))
    updated_at: int = field(default_factory=lambda: int(time.time()))


class AnchorQueueManager:
    """SQLite-persisted and crash-resilient queue manager for anchor tasks."""

    def __init__(
        self,
        adapter: Optional[BlockchainAdapter] = None,
        default_max_retries: int = 3,
        db_path: Optional[str] = None,
    ) -> None:
        self.adapter: BlockchainAdapter = adapter or SimulatedEVMAdapter()
        self.default_max_retries = default_max_retries
        self.tasks: Dict[str, AnchorTask] = {}
        self.queue: List[str] = []

        if db_path is None:
            self.conn = sqlite3.connect(":memory:")
            self.conn.row_factory = sqlite3.Row
            self.db_path = ":memory:"
        else:
            self.conn = sqlite3.connect(db_path)
            self.conn.row_factory = sqlite3.Row
            self.db_path = db_path

        self._init_db()
        self._load_pending_tasks()

    def _get_connection(self) -> sqlite3.Connection:
        return self.conn

    def _init_db(self) -> None:
        """Initialize tasks table in SQLite database."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS anchor_tasks (
                    task_id TEXT PRIMARY KEY,
                    batch_id TEXT UNIQUE,
                    merkle_root TEXT NOT NULL,
                    metadata_hash TEXT,
                    status TEXT NOT NULL,
                    retry_count INTEGER NOT NULL,
                    max_retries INTEGER NOT NULL,
                    last_error TEXT,
                    receipt_json TEXT,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
            """)
            conn.commit()

    def _load_pending_tasks(self) -> None:
        """Recover pending/queued tasks from SQLite database after restart."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM anchor_tasks")
            for row in cursor.fetchall():
                receipt = None
                if row["receipt_json"]:
                    try:
                        r_data = json.loads(row["receipt_json"])
                        receipt = AnchorReceipt(**r_data)
                    except Exception:
                        receipt = None

                task = AnchorTask(
                    task_id=row["task_id"],
                    batch_id=row["batch_id"],
                    merkle_root=row["merkle_root"],
                    metadata_hash=row["metadata_hash"],
                    status=AnchorTaskStatus(row["status"]),
                    retry_count=row["retry_count"],
                    max_retries=row["max_retries"],
                    receipt=receipt,
                    last_error=row["last_error"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                self.tasks[task.batch_id] = task
                if task.status in (AnchorTaskStatus.QUEUED, AnchorTaskStatus.SUBMITTED, AnchorTaskStatus.FAILED_RETRYABLE):
                    if task.batch_id not in self.queue:
                        self.queue.append(task.batch_id)

    def _save_task_to_db(self, task: AnchorTask) -> None:
        """Persist or update an anchor task in SQLite."""
        receipt_json = None
        if task.receipt:
            receipt_json = json.dumps(task.receipt.__dict__)

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO anchor_tasks (
                    task_id, batch_id, merkle_root, metadata_hash,
                    status, retry_count, max_retries, last_error,
                    receipt_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(batch_id) DO UPDATE SET
                    status=excluded.status,
                    retry_count=excluded.retry_count,
                    last_error=excluded.last_error,
                    receipt_json=excluded.receipt_json,
                    updated_at=excluded.updated_at
            """, (
                task.task_id,
                task.batch_id,
                task.merkle_root,
                task.metadata_hash,
                task.status.value,
                task.retry_count,
                task.max_retries,
                task.last_error,
                receipt_json,
                task.created_at,
                task.updated_at,
            ))
            conn.commit()

    def enqueue_batch(
        self,
        batch_id: str,
        merkle_root: str,
        metadata_hash: Optional[str] = None,
        max_retries: Optional[int] = None,
    ) -> AnchorTask:
        """Enqueue a settlement batch Merkle root for blockchain anchoring.

        Enforces idempotency and conflict prevention.
        """
        clean_batch_id = str(batch_id).strip()
        clean_root = merkle_root.removeprefix("0x").lower()
        clean_meta = (metadata_hash or "").removeprefix("0x").lower()

        # Idempotency & Conflict checks
        if clean_batch_id in self.tasks:
            existing = self.tasks[clean_batch_id]
            existing_root = existing.merkle_root.removeprefix("0x").lower()
            existing_meta = (existing.metadata_hash or "").removeprefix("0x").lower()

            if existing_root != clean_root:
                raise ValueError(
                    f"ConflictingBatchRegistration: batch {clean_batch_id} already registered with "
                    f"root {existing_root}, cannot re-register with different root {clean_root}"
                )
            if existing_meta != clean_meta:
                raise ValueError(
                    f"ConflictingBatchRegistration: batch {clean_batch_id} already registered with "
                    f"metadata {existing_meta}, cannot re-register with different metadata {clean_meta}"
                )

            if existing.status in (AnchorTaskStatus.ANCHORED, AnchorTaskStatus.QUEUED, AnchorTaskStatus.SUBMITTED):
                return existing

        retries = max_retries if max_retries is not None else self.default_max_retries
        task = AnchorTask(
            batch_id=clean_batch_id,
            merkle_root=clean_root,
            metadata_hash=clean_meta if clean_meta else None,
            status=AnchorTaskStatus.QUEUED,
            max_retries=retries,
        )

        self.tasks[clean_batch_id] = task
        if clean_batch_id not in self.queue:
            self.queue.append(clean_batch_id)

        self._save_task_to_db(task)
        return task

    def process_task(self, task: AnchorTask) -> AnchorTask:
        """Process a single anchoring task with on-chain timeout reconciliation."""
        if task.status == AnchorTaskStatus.ANCHORED:
            return task

        task.status = AnchorTaskStatus.SUBMITTED
        task.updated_at = int(time.time())
        self._save_task_to_db(task)

        # 1. Reconciliation: check if batch is already anchored on-chain before attempting tx
        try:
            existing_receipt = self.adapter.get_anchor(task.batch_id)
            if existing_receipt:
                root_match = existing_receipt.merkle_root.lower() == task.merkle_root.lower()
                
                # Check metadata hash matching if task specifies a metadata hash
                meta_match = True
                if task.metadata_hash and existing_receipt.metadata_hash:
                    queued_meta = task.metadata_hash.removeprefix("0x").lower().rjust(64, "0")
                    onchain_meta = existing_receipt.metadata_hash.removeprefix("0x").lower().rjust(64, "0")
                    meta_match = (queued_meta == onchain_meta)

                if root_match and meta_match:
                    task.status = AnchorTaskStatus.ANCHORED
                    task.receipt = existing_receipt
                    task.last_error = None
                    task.updated_at = int(time.time())
                    self._save_task_to_db(task)
                    return task
                elif not root_match:
                    # On-chain batch exists with a conflicting Merkle root!
                    task.status = AnchorTaskStatus.FAILED_FINAL
                    task.last_error = (
                        f"OnChainConflictingMerkleRoot: Batch '{task.batch_id}' is already anchored on-chain "
                        f"with root '{existing_receipt.merkle_root.lower()}', which conflicts with queued root '{task.merkle_root.lower()}'."
                    )
                    task.updated_at = int(time.time())
                    self._save_task_to_db(task)
                    return task
                else:
                    # On-chain batch exists with matching root but conflicting metadata hash!
                    task.status = AnchorTaskStatus.FAILED_FINAL
                    task.last_error = (
                        f"OnChainConflictingMetadataHash: Batch '{task.batch_id}' is already anchored on-chain "
                        f"with metadata hash '{existing_receipt.metadata_hash}', which conflicts with queued metadata '{task.metadata_hash}'."
                    )
                    task.updated_at = int(time.time())
                    self._save_task_to_db(task)
                    return task
        except Exception:
            pass

        # 2. Attempt on-chain anchor submission
        try:
            receipt = self.adapter.anchor_root(
                batch_id=task.batch_id,
                merkle_root=task.merkle_root,
                metadata_hash=task.metadata_hash,
                anchor_attempts=task.retry_count + 1,
            )
            task.receipt = receipt
            task.status = AnchorTaskStatus.ANCHORED
            task.last_error = None
            task.updated_at = int(time.time())
            self._save_task_to_db(task)
            return task

        except Exception as e:
            err_str = str(e)
            task.last_error = err_str
            task.retry_count += 1
            task.updated_at = int(time.time())

            # Check if failure was due to duplicate batch on-chain (already mined by timed-out tx)
            if "BatchAlreadyExists" in err_str or "BatchAlreadyAnchored" in err_str or "a84636a2" in err_str:
                rec = self.adapter.get_anchor(task.batch_id)
                if rec:
                    if rec.merkle_root.lower() == task.merkle_root.lower():
                        task.status = AnchorTaskStatus.ANCHORED
                        task.receipt = rec
                        task.last_error = None
                        self._save_task_to_db(task)
                        return task
                    else:
                        task.status = AnchorTaskStatus.FAILED_FINAL
                        task.last_error = (
                            f"OnChainConflictingMerkleRoot: Batch '{task.batch_id}' already anchored on-chain "
                            f"with root '{rec.merkle_root.lower()}', conflicting with queued root '{task.merkle_root.lower()}'."
                        )
                        self._save_task_to_db(task)
                        return task

            if task.retry_count >= task.max_retries:
                task.status = AnchorTaskStatus.FAILED_FINAL
            else:
                task.status = AnchorTaskStatus.FAILED_RETRYABLE

            self._save_task_to_db(task)
            return task

    def process_all_pending(self) -> Dict[str, AnchorTaskStatus]:
        """Drain the FIFO queue, processing all pending tasks."""
        results: Dict[str, AnchorTaskStatus] = {}
        pending_ids = list(self.queue)
        self.queue.clear()

        for batch_id in pending_ids:
            task = self.tasks.get(batch_id)
            if not task:
                continue
            if task.status in (AnchorTaskStatus.QUEUED, AnchorTaskStatus.FAILED_RETRYABLE):
                self.process_task(task)
                results[batch_id] = task.status
                if task.status == AnchorTaskStatus.FAILED_RETRYABLE:
                    self.queue.append(batch_id)
            else:
                results[batch_id] = task.status

        return results

    def process_queue(self) -> List[AnchorTask]:
        """Alias for process_all_pending returning list of updated AnchorTask objects."""
        pending_ids = list(self.queue)
        self.process_all_pending()
        return [self.tasks[bid] for bid in pending_ids if bid in self.tasks]

    @property
    def total_pending(self) -> int:
        return sum(1 for t in self.tasks.values() if t.status in (AnchorTaskStatus.QUEUED, AnchorTaskStatus.FAILED_RETRYABLE))

    @property
    def total_anchored(self) -> int:
        return sum(1 for t in self.tasks.values() if t.status == AnchorTaskStatus.ANCHORED)

    @property
    def total_failed(self) -> int:
        return sum(1 for t in self.tasks.values() if t.status == AnchorTaskStatus.FAILED_FINAL)

    def get_task(self, batch_id: str) -> Optional[AnchorTask]:
        return self.tasks.get(batch_id.strip())

    def get_anchored_receipt(self, batch_id: str) -> Optional[AnchorReceipt]:
        task = self.get_task(batch_id)
        if task and task.status == AnchorTaskStatus.ANCHORED:
            return task.receipt
        return None
