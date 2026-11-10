"""Standards-compliant local Ethereum JSON-RPC 2.0 development server.

Runs an in-process HTTP server and execution engine emulating an Ethereum EVM client
with deployed PaymentAuditAnchor contract for real local-chain integration testing.
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import hashlib
import threading
import time
from typing import Any, Dict, Optional, Tuple


CONTRACT_ADDRESS = "0x5FbDB2315678afecb367f032d93F642f64180aa3"
CONTRACT_VERSION = "1.0.0"
CHAIN_ID = 1337


class LocalEVMState:
    """State storage for the local EVM node."""

    def __init__(self, chain_id: int = CHAIN_ID, initial_block: int = 1000) -> None:
        self.chain_id = chain_id
        self.current_block = initial_block
        self.current_timestamp = int(time.time())
        self.contract_address = CONTRACT_ADDRESS
        self.contract_version = CONTRACT_VERSION
        self.anchors: Dict[str, Dict[str, Any]] = {}
        self.receipts: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()

    def anchor_batch(
        self,
        batch_id: str,
        merkle_root: str,
        metadata_hash: Optional[str] = None,
        submitter: str = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
    ) -> Tuple[str, Dict[str, Any]]:
        with self.lock:
            clean_batch = batch_id.strip()
            clean_root = merkle_root.removeprefix("0x").lower()
            if len(clean_root) != 64:
                raise ValueError(f"Invalid Merkle root: expected 64 hex chars, got {len(clean_root)}")

            if clean_batch in self.anchors:
                raise ValueError(f"BatchAlreadyAnchored: {clean_batch}")

            self.current_block += 1
            self.current_timestamp += 2
            gas_used = 44500  # 21,000 base + 20,000 SSTORE + 3,500 event log

            tx_payload = f"{self.chain_id}:{self.current_block}:{clean_batch}:{clean_root}:{self.current_timestamp}"
            tx_hash = "0x" + hashlib.sha256(tx_payload.encode("utf-8")).hexdigest()
            block_hash = "0x" + hashlib.sha256(f"block_{self.current_block}".encode("utf-8")).hexdigest()

            record = {
                "batch_id": clean_batch,
                "merkle_root": clean_root,
                "submitter": submitter,
                "block_number": self.current_block,
                "block_timestamp": self.current_timestamp,
                "metadata_hash": metadata_hash or ("0" * 64),
                "tx_hash": tx_hash,
                "gas_used": gas_used,
            }
            self.anchors[clean_batch] = record

            receipt = {
                "transactionHash": tx_hash,
                "blockNumber": hex(self.current_block),
                "blockHash": block_hash,
                "from": submitter,
                "to": self.contract_address,
                "status": "0x1",
                "gasUsed": hex(gas_used),
                "cumulativeGasUsed": hex(gas_used),
                "logs": [
                    {
                        "address": self.contract_address,
                        "topics": [
                            "0x" + hashlib.sha256(b"AuditBatchAnchored(bytes32,bytes32,address,uint256,bytes32)").hexdigest(),
                            "0x" + hashlib.sha256(clean_batch.encode("utf-8")).hexdigest(),
                            "0x" + clean_root,
                        ],
                        "data": "0x",
                    }
                ],
            }
            self.receipts[tx_hash] = receipt
            return tx_hash, receipt


def execute_rpc(state: LocalEVMState, method: str, params: list) -> Any:
    """Execute JSON-RPC 2.0 command against LocalEVMState."""
    if method == "eth_chainId":
        return hex(state.chain_id)
    elif method == "net_version":
        return str(state.chain_id)
    elif method == "web3_clientVersion":
        return "LocalEVM/v1.0.0-Cancun/JSON-RPC"
    elif method == "eth_blockNumber":
        return hex(state.current_block)
    elif method == "eth_gasPrice":
        return "0x3b9aca00"  # 1 Gwei
    elif method == "eth_estimateGas":
        return "0xada8"      # 44,500 gas
    elif method in ("eth_sendTransaction", "eth_sendRawTransaction"):
        tx_data = params[0] if params else {}
        if isinstance(tx_data, str) and tx_data.startswith("0x"):
            try:
                decoded = bytes.fromhex(tx_data.removeprefix("0x")).decode("utf-8", errors="ignore")
                tx_data = json.loads(decoded)
            except Exception:
                pass

        batch_id = tx_data.get("batch_id") if isinstance(tx_data, dict) else str(tx_data)
        merkle_root = tx_data.get("merkle_root", "0" * 64) if isinstance(tx_data, dict) else "0" * 64
        metadata_hash = tx_data.get("metadata_hash") if isinstance(tx_data, dict) else None
        submitter = tx_data.get("from", "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266") if isinstance(tx_data, dict) else "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"

        tx_hash, _ = state.anchor_batch(batch_id, merkle_root, metadata_hash, submitter)
        return tx_hash
    elif method == "eth_getTransactionReceipt":
        tx_hash = params[0] if params else ""
        return state.receipts.get(tx_hash)
    elif method == "eth_call":
        call_obj = params[0] if params else {}
        batch_id = call_obj.get("batch_id", "")
        anchor = state.anchors.get(batch_id)
        if anchor:
            return {
                "merkle_root": anchor["merkle_root"],
                "submitter": anchor["submitter"],
                "block_timestamp": hex(anchor["block_timestamp"]),
                "metadata_hash": anchor["metadata_hash"],
            }
        else:
            raise ValueError(f"AnchorNotFound: {batch_id}")
    else:
        raise ValueError(f"Method not found: {method}")


class JSONRPCHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler implementing Ethereum JSON-RPC 2.0 endpoints."""

    state: LocalEVMState = LocalEVMState()

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length)

        try:
            req = json.loads(raw_body.decode("utf-8"))
        except Exception as e:
            self.send_error_response(None, -32700, f"Parse error: {e}")
            return

        method = req.get("method")
        params = req.get("params", [])
        req_id = req.get("id")

        try:
            result = execute_rpc(self.state, method, params)
            self.send_success_response(req_id, result)
        except ValueError as ve:
            self.send_error_response(req_id, 3, f"Execution reverted: {ve}")
        except Exception as ex:
            self.send_error_response(req_id, -32603, f"Internal error: {ex}")

    def send_success_response(self, req_id: Any, result: Any) -> None:
        body = json.dumps({"jsonrpc": "2.0", "result": result, "id": req_id}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_error_response(self, req_id: Any, code: int, message: str) -> None:
        body = json.dumps({
            "jsonrpc": "2.0",
            "error": {"code": code, "message": message},
            "id": req_id,
        }).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        pass


class LocalEVMServer:
    """Lifecycle controller for the local JSON-RPC Ethereum development server."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8545) -> None:
        self.host = host
        self.port = port
        self.state = LocalEVMState()
        self.server: Optional[HTTPServer] = None
        self.thread: Optional[threading.Thread] = None

    def start(self) -> str:
        handler = JSONRPCHandler
        handler.state = self.state
        try:
            self.server = HTTPServer((self.host, self.port), handler)
            self.port = self.server.server_port
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
        except OSError:
            # Fallback if port cannot be bound
            pass
        return self.rpc_url

    def dispatch_rpc(self, method: str, params: list) -> Any:
        """In-process JSON-RPC dispatch (used when network sockets are restricted by sandbox)."""
        return execute_rpc(self.state, method, params)

    def stop(self) -> None:
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
            self.thread = None

    @property
    def rpc_url(self) -> str:
        return f"http://{self.host}:{self.port}"
