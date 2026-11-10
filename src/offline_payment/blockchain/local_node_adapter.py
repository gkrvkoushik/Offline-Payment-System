"""Real EVM integration adapters using Web3.py.

Includes:
- EthereumLocalNodeAdapter: Interacts with a genuine local Hardhat or Anvil EVM node.
- ProductionEVMAdapter: Reusable JSON-RPC integration for Ethereum L1/L2 networks.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, cast
from web3 import Web3
from web3.contract import Contract
from web3.types import TxReceipt

from offline_payment.blockchain.adapter import (
    AnchorReceipt,
    BlockchainAdapter,
)
from offline_payment.blockchain.environments import (
    ENV_REAL_LOCAL_HARDHAT_EVM,
    ENV_REAL_LOCAL_ANVIL_EVM,
    ENV_PRODUCTION_EVM_RPC,
)
from offline_payment.blockchain.compiler import compile_anchor_contract


def _to_bytes32(val: str) -> bytes:
    """Convert hex string or text string into exactly 32 bytes."""
    clean = val.removeprefix("0x").strip()
    if len(clean) == 64:
        return bytes.fromhex(clean)
    encoded = clean.encode("utf-8")
    if len(encoded) > 32:
        import hashlib
        return hashlib.sha256(encoded).digest()
    return encoded.ljust(32, b"\x00")


class EthereumLocalNodeAdapter(BlockchainAdapter):
    """Actual EVM integration executing against a genuine local Hardhat or Anvil node.

    Deploys compiled PaymentAuditAnchor.sol bytecode, captures deployment receipts,
    validates deployed bytecode using eth_getCode, submits signed anchor transactions,
    reads actual mined receipts, block numbers, gas usage, and verifies contract state.
    """

    def __init__(
        self,
        rpc_url: str = "http://127.0.0.1:8545",
        contract_address: Optional[str] = None,
        private_key: Optional[str] = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.rpc_url = rpc_url
        self.w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": timeout_seconds}))
        if not self.w3.is_connected():
            raise ConnectionError(f"Cannot connect to local Ethereum node at {rpc_url}")

        self.chain_id = self.w3.eth.chain_id
        self.client_version = self.w3.client_version
        self.execution_environment = (
            ENV_REAL_LOCAL_ANVIL_EVM if "anvil" in self.client_version.lower() else ENV_REAL_LOCAL_HARDHAT_EVM
        )

        # Default Hardhat account #0 and account #1
        self.deployer_account = self.w3.eth.accounts[0] if self.w3.eth.accounts else None
        self.default_account = (
            self.w3.eth.accounts[1] if len(self.w3.eth.accounts) > 1 else self.deployer_account
        )

        self.abi, self.bytecode = compile_anchor_contract()
        self.contract_address = contract_address
        self.deployment_receipt: Optional[TxReceipt] = None

        if not self.contract_address:
            self._deploy_contract()
        else:
            self._verify_deployed_bytecode()

        self.contract: Contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.contract_address),
            abi=self.abi,
        )

    def _deploy_contract(self) -> None:
        """Deploy PaymentAuditAnchor.sol to the local EVM node."""
        factory = self.w3.eth.contract(abi=self.abi, bytecode=self.bytecode)
        tx_hash = factory.constructor().transact({"from": self.deployer_account})
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=10.0)
        if receipt["status"] != 1:
            raise RuntimeError(f"Contract deployment failed! Status: {receipt['status']}")

        self.deployment_receipt = receipt
        self.contract_address = receipt["contractAddress"]
        self._verify_deployed_bytecode()

        # Authorize default submitter account if different from deployer
        if self.default_account and self.default_account != self.deployer_account:
            instance = self.w3.eth.contract(
                address=Web3.to_checksum_address(self.contract_address),
                abi=self.abi,
            )
            auth_tx = instance.functions.addAuthorizedSubmitter(
                Web3.to_checksum_address(self.default_account)
            ).transact({"from": self.deployer_account})
            self.w3.eth.wait_for_transaction_receipt(auth_tx, timeout=10.0)

    def _verify_deployed_bytecode(self) -> None:
        """Verify on-chain contract bytecode using eth_getCode."""
        code = self.w3.eth.get_code(Web3.to_checksum_address(self.contract_address))
        if not code or code == b"" or code.hex() in ("0x", ""):
            raise RuntimeError(f"No contract bytecode deployed at {self.contract_address}")

    def anchor_root(
        self,
        batch_id: str,
        merkle_root: str,
        metadata_hash: Optional[str] = None,
        submitter: Optional[str] = None,
        event_count: int = 0,
        anchor_attempts: int = 1,
    ) -> AnchorReceipt:
        sender = submitter or self.default_account or self.deployer_account
        clean_batch_bytes = _to_bytes32(batch_id)
        clean_root_bytes = _to_bytes32(merkle_root)
        clean_meta_bytes = _to_bytes32(metadata_hash or "0" * 64)

        sender_checksum = Web3.to_checksum_address(sender)

        # Estimate gas using eth_estimateGas
        try:
            gas_estimate = self.contract.functions.anchorBatch(
                clean_batch_bytes,
                clean_root_bytes,
                clean_meta_bytes,
            ).estimate_gas({"from": sender_checksum})
        except Exception:
            gas_estimate = 100000

        # Send transaction
        tx_hash = self.contract.functions.anchorBatch(
            clean_batch_bytes,
            clean_root_bytes,
            clean_meta_bytes,
        ).transact({
            "from": sender_checksum,
            "gas": int(gas_estimate * 1.2),
        })

        receipt: TxReceipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=10.0)
        if receipt["status"] != 1:
            raise RuntimeError(f"anchorBatch transaction failed on-chain! Tx: {tx_hash.hex()}")

        block = self.w3.eth.get_block(receipt["blockNumber"])
        latest_block = self.w3.eth.block_number
        confirmations = max(1, latest_block - receipt["blockNumber"] + 1)

        gas_used = receipt["gasUsed"]
        effective_gas_price = receipt.get("effectiveGasPrice", self.w3.eth.gas_price)
        tx_fee = gas_used * effective_gas_price

        return AnchorReceipt(
            batch_id=batch_id,
            merkle_root=merkle_root.removeprefix("0x").lower(),
            tx_hash=receipt["transactionHash"].hex(),
            block_number=receipt["blockNumber"],
            block_timestamp=block["timestamp"],
            gas_used=gas_used,
            submitter=sender,
            status="SUCCESS",
            receipt_status="REAL_LOCAL_EVM_MINED",
            chain_id=self.chain_id,
            contract_address=self.contract_address,
            contract_version="1.0.0",
            confirmation_count=confirmations,
            event_count=event_count,
            anchor_attempts=anchor_attempts,
            execution_environment=self.execution_environment,
            metadata_hash=metadata_hash,
            effective_gas_price_wei=effective_gas_price,
            transaction_fee_wei=tx_fee,
        )

    def get_anchor(self, batch_id: str) -> Optional[AnchorReceipt]:
        clean_batch_bytes = _to_bytes32(batch_id)
        try:
            record = self.contract.functions.getAnchor(clean_batch_bytes).call()
            merkle_root_hex = record[0].hex()
            submitter = record[1]
            block_timestamp = record[2]
            schema_version = record[3]
            metadata_hash_hex = record[4].hex()

            return AnchorReceipt(
                batch_id=batch_id,
                merkle_root=merkle_root_hex,
                tx_hash="",
                block_number=0,
                block_timestamp=block_timestamp,
                gas_used=0,
                submitter=submitter,
                status="SUCCESS",
                receipt_status="REAL_ON_CHAIN_STORED",
                chain_id=self.chain_id,
                contract_address=self.contract_address,
                contract_version=str(schema_version),
                confirmation_count=1,
                execution_environment=self.execution_environment,
                metadata_hash=metadata_hash_hex,
            )
        except Exception:
            return None

    def verify_anchor_exists(self, batch_id: str, expected_root: str) -> bool:
        rec = self.get_anchor(batch_id)
        if rec is None:
            return False
        clean_expected = expected_root.removeprefix("0x").lower()
        return rec.merkle_root.lower() == clean_expected

    def verify_inclusion_on_chain(
        self,
        batch_id: str,
        leaf_hash: str,
        proof: list[str],
        is_left: list[bool],
    ) -> bool:
        """Call verifyInclusion smart contract method to verify SHA-256 Merkle proof on EVM."""
        batch_bytes = _to_bytes32(batch_id)
        leaf_bytes = _to_bytes32(leaf_hash)
        proof_bytes = [_to_bytes32(p) for p in proof]
        return self.contract.functions.verifyInclusion(
            batch_bytes,
            leaf_bytes,
            proof_bytes,
            is_left,
        ).call()


class ProductionEVMAdapter(BlockchainAdapter):
    """Production and public testnet EVM integration adapter using Web3.py.

    Connects to external JSON-RPC endpoints (e.g., Ethereum mainnet, Sepolia, Arbitrum, Optimism).
    Strictly classified as PRODUCTION_EVM_RPC.
    """

    def __init__(
        self,
        rpc_url: str,
        contract_address: str,
        private_key: str,
        abi: Optional[list] = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        self.rpc_url = rpc_url
        self.w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": timeout_seconds}))
        if not self.w3.is_connected():
            raise ConnectionError(f"Cannot connect to production Ethereum node at {rpc_url}")

        self.chain_id = self.w3.eth.chain_id
        self.account = self.w3.eth.account.from_key(private_key)
        self.contract_address = Web3.to_checksum_address(contract_address)

        if abi is None:
            compiled_abi, _ = compile_anchor_contract()
            self.abi = compiled_abi
        else:
            self.abi = abi

        self.contract: Contract = self.w3.eth.contract(address=self.contract_address, abi=self.abi)

    def anchor_root(
        self,
        batch_id: str,
        merkle_root: str,
        metadata_hash: Optional[str] = None,
        submitter: Optional[str] = None,
        event_count: int = 0,
        anchor_attempts: int = 1,
    ) -> AnchorReceipt:
        clean_batch_bytes = _to_bytes32(batch_id)
        clean_root_bytes = _to_bytes32(merkle_root)
        clean_meta_bytes = _to_bytes32(metadata_hash or "0" * 64)

        nonce = self.w3.eth.get_transaction_count(self.account.address)
        gas_price = self.w3.eth.gas_price

        tx = self.contract.functions.anchorBatch(
            clean_batch_bytes,
            clean_root_bytes,
            clean_meta_bytes,
        ).build_transaction({
            "from": self.account.address,
            "nonce": nonce,
            "gasPrice": gas_price,
        })

        signed_tx = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        receipt: TxReceipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60.0)
        if receipt["status"] != 1:
            raise RuntimeError(f"anchorBatch transaction failed on production EVM! Tx: {tx_hash.hex()}")

        block = self.w3.eth.get_block(receipt["blockNumber"])
        latest_block = self.w3.eth.block_number
        confirmations = max(1, latest_block - receipt["blockNumber"] + 1)

        gas_used = receipt["gasUsed"]
        effective_gas_price = receipt.get("effectiveGasPrice", gas_price)
        tx_fee = gas_used * effective_gas_price

        return AnchorReceipt(
            batch_id=batch_id,
            merkle_root=merkle_root.removeprefix("0x").lower(),
            tx_hash=receipt["transactionHash"].hex(),
            block_number=receipt["blockNumber"],
            block_timestamp=block["timestamp"],
            gas_used=gas_used,
            submitter=self.account.address,
            status="SUCCESS",
            receipt_status="PRODUCTION_EVM_CONFIRMED",
            chain_id=self.chain_id,
            contract_address=self.contract_address,
            contract_version="1.0.0",
            confirmation_count=confirmations,
            event_count=event_count,
            anchor_attempts=anchor_attempts,
            execution_environment=ENV_PRODUCTION_EVM_RPC,
            metadata_hash=metadata_hash,
            effective_gas_price_wei=effective_gas_price,
            transaction_fee_wei=tx_fee,
        )

    def get_anchor(self, batch_id: str) -> Optional[AnchorReceipt]:
        clean_batch_bytes = _to_bytes32(batch_id)
        try:
            record = self.contract.functions.getAnchor(clean_batch_bytes).call()
            return AnchorReceipt(
                batch_id=batch_id,
                merkle_root=record[0].hex(),
                tx_hash="",
                block_number=0,
                block_timestamp=record[2],
                gas_used=0,
                submitter=record[1],
                status="SUCCESS",
                receipt_status="PRODUCTION_EVM_STORED",
                chain_id=self.chain_id,
                contract_address=self.contract_address,
                contract_version=str(record[3]),
                confirmation_count=1,
                execution_environment=ENV_PRODUCTION_EVM_RPC,
                metadata_hash=record[4].hex(),
            )
        except Exception:
            return None

    def verify_anchor_exists(self, batch_id: str, expected_root: str) -> bool:
        rec = self.get_anchor(batch_id)
        if rec is None:
            return False
        clean_expected = expected_root.removeprefix("0x").lower()
        return rec.merkle_root.lower() == clean_expected
