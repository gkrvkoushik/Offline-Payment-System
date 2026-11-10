"""Real local-chain integration tests using Ethereum JSON-RPC adapter."""

import pytest
from offline_payment.blockchain import (
    LocalEVMServer,
    JsonRpcBlockchainAdapter,
    CONTRACT_ADDRESS,
    CONTRACT_VERSION,
    CHAIN_ID,
)


@pytest.fixture(scope="module")
def real_local_chain():
    server = LocalEVMServer(host="127.0.0.1", port=0)
    server.start()
    adapter = JsonRpcBlockchainAdapter(server=server, rpc_url=server.rpc_url)
    yield adapter, server
    server.stop()


def test_real_local_chain_connection_and_chain_id(real_local_chain):
    adapter, _ = real_local_chain
    chain_id = adapter.get_chain_id()
    assert chain_id == CHAIN_ID
    block_num = adapter.get_block_number()
    assert block_num >= 1000


def test_real_local_chain_anchor_and_receipt(real_local_chain):
    adapter, _ = real_local_chain
    batch_id = "real_batch_001"
    root = "e" * 64

    receipt = adapter.anchor_root(
        batch_id=batch_id,
        merkle_root=root,
        event_count=15,
        anchor_attempts=1,
    )

    assert receipt.receipt_status == "REAL_CONFIRMED"
    assert receipt.execution_environment == "REAL_LOCAL_JSONRPC_EVM"
    assert receipt.chain_id == CHAIN_ID
    assert receipt.contract_address == CONTRACT_ADDRESS
    assert receipt.contract_version == CONTRACT_VERSION
    assert receipt.actual_gas_used == 44500
    assert receipt.confirmation_count >= 1
    assert receipt.event_count == 15
    assert receipt.anchor_attempts == 1
    assert receipt.transaction_hash.startswith("0x")

    # Verify on-chain query
    stored = adapter.get_anchor(batch_id)
    assert stored is not None
    assert stored.merkle_root.lower() == root.lower()
    assert adapter.verify_anchor_exists(batch_id, root) is True
    assert adapter.verify_anchor_exists(batch_id, "0" * 64) is False


def test_real_local_chain_rejects_duplicates(real_local_chain):
    adapter, _ = real_local_chain
    batch_id = "real_batch_dup"
    root = "f" * 64

    adapter.anchor_root(batch_id=batch_id, merkle_root=root)

    with pytest.raises(ValueError, match="BatchAlreadyAnchored"):
        adapter.anchor_root(batch_id=batch_id, merkle_root=root)


def test_real_local_chain_network_unreachable():
    # Attempt connection to dead URL without in-process server
    dead_adapter = JsonRpcBlockchainAdapter(server=None, rpc_url="http://127.0.0.1:59999", timeout_seconds=1.0)
    with pytest.raises(ConnectionError, match="Failed to connect"):
        dead_adapter.anchor_root("fail_batch", "1" * 64)
