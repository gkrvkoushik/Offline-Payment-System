"""Hardhat local EVM development node process manager.

Launches and manages an in-background Hardhat node on 127.0.0.1:8545
providing genuine EVM execution for local integration testing.
"""

import os
from pathlib import Path
import subprocess
import time
import urllib.request
import json
from typing import Optional

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent.parent
NODE_MODULES_BIN = WORKSPACE_ROOT / "node_modules" / ".bin"


class HardhatNodeProcess:
    """Manages the lifecycle of a real local Hardhat EVM node."""

    def __init__(self, port: int = 8545, host: str = "127.0.0.1") -> None:
        self.port = port
        self.host = host
        self.rpc_url = f"http://{host}:{port}"
        self.process: Optional[subprocess.Popen] = None

    def is_running(self) -> bool:
        """Check if the Hardhat JSON-RPC node is responsive."""
        req_data = json.dumps({
            "jsonrpc": "2.0",
            "method": "eth_chainId",
            "params": [],
            "id": 1,
        }).encode("utf-8")
        req = urllib.request.Request(
            self.rpc_url,
            data=req_data,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return "result" in data
        except Exception:
            return False

    def start(self, timeout_seconds: float = 15.0) -> None:
        """Start the Hardhat node if not already running."""
        if self.is_running():
            return

        cmd = ["npx", "hardhat", "node", "--hostname", self.host, "--port", str(self.port)]
        # On Windows, npx is npx.cmd
        if os.name == "nt":
            cmd[0] = "npx.cmd"

        self.process = subprocess.Popen(
            cmd,
            cwd=str(WORKSPACE_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            if self.is_running():
                return
            if self.process.poll() is not None:
                _, stderr = self.process.communicate()
                raise RuntimeError(f"Hardhat node process exited unexpectedly: {stderr}")
            time.sleep(0.5)

        self.stop()
        raise TimeoutError(f"Hardhat node failed to start within {timeout_seconds}s on {self.rpc_url}")

    def stop(self) -> None:
        """Terminate the Hardhat node process."""
        if self.process is not None:
            try:
                self.process.terminate()
                self.process.wait(timeout=3.0)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None


# Global singleton instance for test runs
_DEFAULT_NODE: Optional[HardhatNodeProcess] = None


def get_or_start_hardhat_node(port: int = 8545) -> HardhatNodeProcess:
    global _DEFAULT_NODE
    if _DEFAULT_NODE is None:
        _DEFAULT_NODE = HardhatNodeProcess(port=port)
    if not _DEFAULT_NODE.is_running():
        _DEFAULT_NODE.start()
    return _DEFAULT_NODE
