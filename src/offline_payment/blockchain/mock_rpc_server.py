"""Custom JSON-RPC server mock for fault-injection testing.

Strictly classified as MOCK_FAULT_INJECTION_RPC.
Provides programmable RPC drops, HTTP 500 errors, timeout emulation,
and malformed JSON responses to test adapter recovery invariants.
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import threading
import time
from typing import Any, Dict, Optional, Tuple

from offline_payment.blockchain.environments import ENV_MOCK_FAULT_INJECTION_RPC

MOCK_CONTRACT_ADDRESS = "0x5FbDB2315678afecb367f032d93F642f64180aa3"
MOCK_CONTRACT_VERSION = "1.0.0-mock-rpc"
MOCK_CHAIN_ID = 1337


class MockRpcState:
    """State storage for the fault injection mock RPC server."""

    def __init__(self, chain_id: int = MOCK_CHAIN_ID, initial_block: int = 1000) -> None:
        self.chain_id = chain_id
        self.current_block = initial_block
        self.current_timestamp = int(time.time())
        self.contract_address = MOCK_CONTRACT_ADDRESS
        self.contract_version = MOCK_CONTRACT_VERSION
        self.anchors: Dict[str, Dict[str, Any]] = {}
        self.receipts: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()

        # Fault injection toggles
        self.drop_connections: bool = False
        self.inject_500_error: bool = False
        self.inject_delay_seconds: float = 0.0
        self.fail_next_n_txs: int = 0


def execute_mock_rpc(state: MockRpcState, method: str, params: list) -> Any:
    """Execute JSON-RPC 2.0 command against MockRpcState."""
    if state.inject_delay_seconds > 0:
        time.sleep(state.inject_delay_seconds)

    if state.inject_500_error:
        raise RuntimeError("Internal server fault injected")

    if method == "eth_chainId":
        return hex(state.chain_id)
    elif method == "net_version":
        return str(state.chain_id)
    elif method == "web3_clientVersion":
        return f"MockJsonRpcServer/{state.contract_version}"
    elif method == "eth_blockNumber":
        return hex(state.current_block)
    elif method == "eth_getCode":
        return "0x608060405234801561001057600080fd5b5061"  # Simulated bytecode
    elif method == "eth_estimateGas":
        return hex(44500)
    elif method == "eth_gasPrice":
        return hex(1_000_000_000)
    elif method == "eth_getTransactionReceipt":
        tx_hash = params[0] if params else ""
        return state.receipts.get(tx_hash)
    elif method == "eth_call":
        call_obj = params[0] if params else {}
        data = call_obj.get("data", "")
        # Emulate getAnchor call
        batch_id = data[10:74] if len(data) >= 74 else ""
        rec = state.anchors.get(batch_id)
        if rec is None:
            return "0x"
        merkle_root = rec["merkle_root"].removeprefix("0x").rjust(64, "0")
        submitter = rec["submitter"].removeprefix("0x").rjust(64, "0")
        block_time = hex(rec["block_timestamp"])[2:].rjust(64, "0")
        schema_ver = hex(1)[2:].rjust(64, "0")
        metadata_hash = rec.get("metadata_hash", "0" * 64).removeprefix("0x").rjust(64, "0")
        return "0x" + merkle_root + submitter + block_time + schema_ver + metadata_hash
    elif method == "eth_sendTransaction" or method == "eth_sendRawTransaction":
        if state.fail_next_n_txs > 0:
            state.fail_next_n_txs -= 1
            raise ValueError("RPC fault injected: transaction rejected")
        tx_hash = "0x" + f"mock_tx_{state.current_block}_{len(state.receipts)}".rjust(64, "0")
        state.current_block += 1
        state.receipts[tx_hash] = {
            "transactionHash": tx_hash,
            "blockNumber": hex(state.current_block),
            "status": "0x1",
            "gasUsed": hex(44500),
            "effectiveGasPrice": hex(1_000_000_000),
        }
        return tx_hash
    else:
        raise ValueError(f"Method {method} not supported by MockJsonRpcServer")


class MockJsonRpcHandler(BaseHTTPRequestHandler):
    """HTTP request handler for mock JSON-RPC server."""

    def log_message(self, format: str, *args: Any) -> None:
        pass

    def do_POST(self) -> None:
        server: MockJsonRpcServer = self.server  # type: ignore
        state = server.state

        if state.drop_connections:
            self.close_connection = True
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            req = json.loads(body.decode("utf-8"))
            method = req.get("method", "")
            params = req.get("params", [])
            req_id = req.get("id")

            result = execute_mock_rpc(state, method, params)
            response = {"jsonrpc": "2.0", "id": req_id, "result": result}
            resp_bytes = json.dumps(response).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp_bytes)))
            self.end_headers()
            self.wfile.write(resp_bytes)
        except Exception as e:
            err_resp = {
                "jsonrpc": "2.0",
                "id": req.get("id") if "req" in locals() else None,
                "error": {"code": -32000, "message": str(e)},
            }
            resp_bytes = json.dumps(err_resp).encode("utf-8")
            self.send_response(500 if state.inject_500_error else 200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp_bytes)))
            self.end_headers()
            self.wfile.write(resp_bytes)


class MockJsonRpcServer(HTTPServer):
    """Embedded mock JSON-RPC server for fault-injection testing."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8546) -> None:
        self.state = MockRpcState()
        super().__init__((host, port), MockJsonRpcHandler)
        self._thread: Optional[threading.Thread] = None

    def start_background(self) -> None:
        self._thread = threading.Thread(target=self.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.shutdown()
        self.server_close()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
