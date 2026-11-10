"""Solidity compiler integration using py-solc-x.

Compiles PaymentAuditAnchor.sol with solc 0.8.20 and generates/loads
build artifacts (ABI and Bytecode) for local deployment.
"""

import json
from pathlib import Path
from typing import Any, Dict, Tuple
import solcx

CONTRACTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "blockchain" / "contracts"
BUILD_DIR = Path(__file__).resolve().parent.parent.parent.parent / "blockchain" / "build"
CONTRACT_FILE = CONTRACTS_DIR / "PaymentAuditAnchor.sol"
OUTPUT_FILE = BUILD_DIR / "PaymentAuditAnchor.json"
SOLC_VERSION = "0.8.20"


def compile_anchor_contract(force_recompile: bool = False) -> Tuple[Dict[str, Any], str]:
    """Compile PaymentAuditAnchor.sol and return (abi, bytecode).

    Caches the compilation output in blockchain/build/PaymentAuditAnchor.json.
    """
    if not force_recompile and OUTPUT_FILE.exists():
        try:
            data = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
            if "abi" in data and "bytecode" in data and len(data["bytecode"]) > 10:
                return data["abi"], data["bytecode"]
        except Exception:
            pass

    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    installed_versions = [str(v) for v in solcx.get_installed_solc_versions()]
    if SOLC_VERSION not in installed_versions:
        solcx.install_solc(SOLC_VERSION)
    solcx.set_solc_version(SOLC_VERSION)

    compiled = solcx.compile_files(
        [str(CONTRACT_FILE)],
        output_values=["abi", "bin"],
        solc_version=SOLC_VERSION,
        optimize=True,
        optimize_runs=200,
    )

    contract_key = f"{CONTRACT_FILE}:PaymentAuditAnchor"
    if contract_key not in compiled:
        # Fallback to key matching by contract name
        matching_keys = [k for k in compiled.keys() if k.endswith(":PaymentAuditAnchor")]
        if not matching_keys:
            raise RuntimeError(f"Contract PaymentAuditAnchor not found in compiled keys: {list(compiled.keys())}")
        contract_key = matching_keys[0]

    contract_interface = compiled[contract_key]
    abi = contract_interface["abi"]
    bytecode = contract_interface["bin"]

    artifact = {
        "contractName": "PaymentAuditAnchor",
        "abi": abi,
        "bytecode": bytecode if bytecode.startswith("0x") else "0x" + bytecode,
        "compilerVersion": SOLC_VERSION,
    }

    OUTPUT_FILE.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    return artifact["abi"], artifact["bytecode"]


if __name__ == "__main__":
    abi, bytecode = compile_anchor_contract(force_recompile=True)
    print(f"Compilation successful! ABI entries: {len(abi)}, Bytecode length: {len(bytecode)} hex characters.")
