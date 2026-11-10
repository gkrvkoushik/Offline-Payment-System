"""Blockchain adapter interface and data structures."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import hashlib
import time
from typing import Dict, List, Optional
import uuid

from offline_payment.blockchain.environments import (
    ENV_MOCK_SIMULATED_EVM,
    ENV_REAL_LOCAL_HARDHAT_EVM,
    ENV_PRODUCTION_EVM_RPC,
)


@dataclass
class AnchorReceipt:
    """Receipt returned when an audit batch root is anchored to the blockchain."""
    batch_id: str
    merkle_root: str
    tx_hash: str
    block_number: int
    block_timestamp: int
    gas_used: int
    submitter: str
    status: str = "SUCCESS"
    receipt_status: str = "REAL_LOCAL_EVM_MINED"
    chain_id: int = 31337
    contract_address: str = "0x5FbDB2315678afecb367f032d93F642f64180aa3"
    contract_version: str = "1.0.0"
    confirmation_count: int = 1
    event_count: int = 0
    anchor_attempts: int = 1
    execution_environment: str = ENV_REAL_LOCAL_HARDHAT_EVM
    metadata_hash: Optional[str] = None
    effective_gas_price_wei: int = 0
    transaction_fee_wei: int = 0

    @property
    def transaction_hash(self) -> str:
        return self.tx_hash

    @property
    def actual_gas_used(self) -> int:
        return self.gas_used


class BlockchainAdapter(ABC):
    """Abstract base class for blockchain audit anchoring adapters."""

    @abstractmethod
    def anchor_root(
        self,
        batch_id: str,
        merkle_root: str,
        metadata_hash: Optional[str] = None,
        submitter: Optional[str] = None,
        event_count: int = 0,
        anchor_attempts: int = 1,
    ) -> AnchorReceipt:
        """Anchor a 32-byte Merkle root onto the blockchain."""
        pass

    @abstractmethod
    def get_anchor(self, batch_id: str) -> Optional[AnchorReceipt]:
        """Fetch an anchored receipt by batch ID."""
        pass

    @abstractmethod
    def verify_anchor_exists(self, batch_id: str, expected_root: str) -> bool:
        """Check if a batch ID exists on-chain with the expected Merkle root."""
        pass


class SimulatedEVMAdapter(BlockchainAdapter):
    """Deterministic in-memory EVM blockchain simulator.

    Strictly classified as MOCK_SIMULATED_EVM.
    Used for fast, zero-dependency unit tests of core offline settlement logic.
    Never reports receipts as REAL or production on-chain transactions.
    """

    BASE_TX_GAS: int = 21000
    SSTORE_GAS: int = 20000
    EVENT_LOG_GAS: int = 3500

    def __init__(
        self,
        chain_id: int = 1337,
        initial_block: int = 1000,
        default_submitter: str = "0xSettlementOperator00000000000000000001",
    ) -> None:
        self.chain_id = chain_id
        self.current_block = initial_block
        self.current_timestamp = int(time.time())
        self.default_submitter = default_submitter
        self.anchors: Dict[str, AnchorReceipt] = {}
        self.tx_history: List[AnchorReceipt] = []

        # Fault injection toggles
        self.network_down: bool = False
        self.fail_next_n_calls: int = 0

    def anchor_root(
        self,
        batch_id: str,
        merkle_root: str,
        metadata_hash: Optional[str] = None,
        submitter: Optional[str] = None,
        event_count: int = 0,
        anchor_attempts: int = 1,
    ) -> AnchorReceipt:
        if self.network_down:
            raise ConnectionError("Blockchain RPC unreachable: Simulated network outage")
        if self.fail_next_n_calls > 0:
            self.fail_next_n_calls -= 1
            raise TimeoutError("Blockchain RPC timeout: Simulated timeout responding to eth_sendRawTransaction")

        clean_batch = batch_id.strip()
        clean_root = merkle_root.removeprefix("0x").lower()
        if len(clean_root) != 64:
            raise ValueError(f"Invalid Merkle root: expected 64 hex chars, got {len(clean_root)}")

        if clean_batch in self.anchors:
            raise ValueError(f"Batch {clean_batch} is already anchored on-chain")

        self.current_block += 1
        self.current_timestamp += 2
        gas_used = self.BASE_TX_GAS + self.SSTORE_GAS + self.EVENT_LOG_GAS

        tx_payload = f"{self.chain_id}:{self.current_block}:{clean_batch}:{clean_root}:{self.current_timestamp}"
        tx_hash = "0x" + hashlib.sha256(tx_payload.encode("utf-8")).hexdigest()

        receipt = AnchorReceipt(
            batch_id=clean_batch,
            merkle_root=clean_root,
            tx_hash=tx_hash,
            block_number=self.current_block,
            block_timestamp=self.current_timestamp,
            gas_used=gas_used,
            submitter=submitter or self.default_submitter,
            status="SUCCESS",
            receipt_status="SIMULATED_MOCK_ANCHORED",
            chain_id=self.chain_id,
            contract_address="0xMockPaymentAuditAnchor0000000000000001",
            contract_version="1.0.0-mock",
            confirmation_count=1,
            event_count=event_count,
            anchor_attempts=anchor_attempts,
            execution_environment=ENV_MOCK_SIMULATED_EVM,
            metadata_hash=metadata_hash,
            effective_gas_price_wei=1_000_000_000,
            transaction_fee_wei=gas_used * 1_000_000_000,
        )

        self.anchors[clean_batch] = receipt
        self.tx_history.append(receipt)
        return receipt

    def get_anchor(self, batch_id: str) -> Optional[AnchorReceipt]:
        if self.network_down:
            raise ConnectionError("SimulatedEVM: Network is unreachable.")
        return self.anchors.get(batch_id.strip())

    def verify_anchor_exists(self, batch_id: str, expected_root: str) -> bool:
        rec = self.get_anchor(batch_id)
        if rec is None:
            return False
        clean_expected = expected_root.removeprefix("0x").lower()
        return rec.merkle_root.lower() == clean_expected
