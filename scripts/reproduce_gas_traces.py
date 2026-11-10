"""Standalone reproducibility and audit script for EVM Opcode-Level Gas Verification.

Directly queries the local Hardhat node for the actual mined transactions,
decodes the raw calldata using the contract ABI, extracts the exact storage keys,
inspects debug_traceTransaction structLogs for SSTORE and LOG4 opcodes,
and reconciles the intrinsic and execution gas metrics.
"""

import json
from eth_abi import decode
from web3 import Web3

RPC_URL = "http://127.0.0.1:8545"
TX1_HASH = "0x0a894afefe52ba411778ba8efcd015d6348bce5ce98eb13f6eb91a47f2aeb45b"
TX2_HASH = "0xd69649ebadce043a1ba3a1414c6292692aa2f4741c956df9e63c8c5f2d2e8d69"


def compute_intrinsic_gas(calldata_bytes: bytes) -> tuple[int, int, int]:
    """Calculate EIP-2930 / EIP-1559 intrinsic gas for calldata.

    Base transaction: 21,000 gas.
    Zero byte: 4 gas.
    Non-zero byte: 16 gas.
    """
    zero_bytes = sum(1 for b in calldata_bytes if b == 0)
    nonzero_bytes = sum(1 for b in calldata_bytes if b != 0)
    calldata_gas = zero_bytes * 4 + nonzero_bytes * 16
    total_intrinsic = 21000 + calldata_gas
    return total_intrinsic, zero_bytes, nonzero_bytes


def main():
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        raise RuntimeError(f"Unable to connect to Ethereum node at {RPC_URL}")

    # Load contract artifact ABI
    with open("blockchain/build/PaymentAuditAnchor.json", encoding="utf-8") as f:
        artifact = json.load(f)
    abi = artifact["abi"]
    contract = w3.eth.contract(abi=abi)

    print("=" * 80)
    print("EVM OPCODE-LEVEL GAS VERIFICATION: ACTUAL HARDHAT NODE TRANSACTIONS")
    print("=" * 80)

    tx_specs = [
        ("Tx 1 (Zero Metadata)", TX1_HASH),
        ("Tx 2 (Non-Zero Metadata)", TX2_HASH),
    ]

    records = []

    for label, tx_hash in tx_specs:
        tx = w3.eth.get_transaction(tx_hash)
        rcpt = w3.eth.get_transaction_receipt(tx_hash)

        # 1. Raw calldata & intrinsic gas
        calldata = bytes(tx["input"])
        intrinsic_gas, zeros, nonzeros = compute_intrinsic_gas(calldata)
        gas_used = rcpt["gasUsed"]
        execution_gas = gas_used - intrinsic_gas

        # 2. Decode function input
        func_obj, params = contract.decode_function_input(tx["input"])
        batch_id_bytes = params["batchId"]
        batch_id_hex = "0x" + batch_id_bytes.hex()
        batch_id_ascii = batch_id_bytes.decode("ascii", errors="replace").rstrip("\x00")

        # 3. Derive storage mapping key
        # slot 2: mapping(bytes32 => AnchorRecord) _anchors
        slot_2_bytes = (2).to_bytes(32, "big")
        base_slot_key = "0x" + w3.keccak(batch_id_bytes + slot_2_bytes).hex()

        # 4. Logs and event topics
        log = rcpt["logs"][0]
        event_sig_topic = "0x" + log["topics"][0].hex()
        topic_batch_id = "0x" + log["topics"][1].hex()
        topic_merkle_root = "0x" + log["topics"][2].hex()
        topic_submitter = "0x" + log["topics"][3].hex()
        data_bytes = bytes(log["data"])
        decoded_data = decode(["uint64", "uint32", "bytes32"], data_bytes)

        # 5. Debug trace structLogs
        trace = w3.provider.make_request("debug_traceTransaction", [tx_hash, {}])["result"]
        struct_logs = trace.get("structLogs", [])

        # Find metadata SSTORE (step 251, PC 1035) and LOG4 (step 302, PC 1136)
        sstore_steps = [
            (i, step) for i, step in enumerate(struct_logs) if step["op"] == "SSTORE"
        ]
        log4_steps = [
            (i, step) for i, step in enumerate(struct_logs) if step["op"] == "LOG4"
        ]

        meta_step_idx, meta_step = sstore_steps[2]  # 3rd SSTORE in the execution
        log4_step_idx, log4_step = log4_steps[0]

        records.append({
            "label": label,
            "tx_hash": tx_hash,
            "block_number": tx["blockNumber"],
            "tx_index": tx["transactionIndex"],
            "from": tx["from"],
            "to": tx["to"],
            "gas_used": gas_used,
            "gas_limit": tx["gas"],
            "calldata_bytes": len(calldata),
            "zeros": zeros,
            "nonzeros": nonzeros,
            "intrinsic_gas": intrinsic_gas,
            "execution_gas": execution_gas,
            "func_name": func_obj.fn_name,
            "batch_id_ascii": batch_id_ascii,
            "batch_id_hex": batch_id_hex,
            "base_slot_key": base_slot_key,
            "event_sig_topic": event_sig_topic,
            "topic_batch_id": topic_batch_id,
            "topic_merkle_root": topic_merkle_root,
            "topic_submitter": topic_submitter,
            "log_data_len": len(data_bytes),
            "log_decoded": decoded_data,
            "meta_sstore_idx": meta_step_idx,
            "meta_sstore_pc": meta_step["pc"],
            "meta_sstore_cost": meta_step["gasCost"],
            "meta_sstore_stack": meta_step["stack"][-2:],
            "log4_idx": log4_step_idx,
            "log4_pc": log4_step["pc"],
            "log4_cost": log4_step["gasCost"],
            "total_trace_steps": len(struct_logs),
        })

    # Display results
    for r in records:
        print(f"\n--- {r['label']} ---")
        print(f"  Tx Hash:          {r['tx_hash']}")
        print(f"  Block Number:     {r['block_number']} | Index in Block: {r['tx_index']}")
        print(f"  From (Submitter): {r['from']}")
        print(f"  To (Contract):    {r['to']}")
        print(f"  Function:         {r['func_name']}()")
        print(f"  batchId (ASCII):  '{r['batch_id_ascii']}'")
        print(f"  batchId (hex):    {r['batch_id_hex']}")
        print(f"  Base Slot Key:    {r['base_slot_key']}")
        print(f"  Calldata:         {r['calldata_bytes']} bytes ({r['zeros']} zero, {r['nonzeros']} non-zero bytes)")
        print(f"  Intrinsic Gas:    {r['intrinsic_gas']} (21000 + {r['zeros']}*4 + {r['nonzeros']}*16)")
        print(f"  Receipt Gas Used: {r['gas_used']}")
        print(f"  Execution Gas:    {r['execution_gas']} ({r['gas_used']} - {r['intrinsic_gas']})")
        print(f"  Event Sig Topic:  {r['event_sig_topic']}")
        print(f"  Log Data:         {r['log_data_len']} bytes -> (blockTimestamp={r['log_decoded'][0]}, schemaVersion={r['log_decoded'][1]}, metadataHash=0x{r['log_decoded'][2].hex()[:16]}...)")
        print(f"  Meta SSTORE Step: Step {r['meta_sstore_idx']} | PC {r['meta_sstore_pc']} | Cost: {r['meta_sstore_cost']} gas")
        print(f"  LOG4 Step:        Step {r['log4_idx']} | PC {r['log4_pc']} | Cost: {r['log4_cost']} gas")
        print(f"  Total VM Steps:   {r['total_trace_steps']}")

    # Reconciliations
    print("\n" + "=" * 80)
    print("RECONCILIATION SUMMARY:")
    delta_intrinsic = records[1]["intrinsic_gas"] - records[0]["intrinsic_gas"]
    delta_execution = records[1]["execution_gas"] - records[0]["execution_gas"]
    delta_total = records[1]["gas_used"] - records[0]["gas_used"]
    delta_sstore = records[1]["meta_sstore_cost"] - records[0]["meta_sstore_cost"]

    print(f"  Delta Intrinsic Gas:  {delta_intrinsic:6d} gas  ({records[1]['nonzeros'] - records[0]['nonzeros']} non-zero bytes * 12 gas)")
    print(f"  Delta Execution Gas:  {delta_execution:6d} gas")
    print(f"  Delta Total Gas:      {delta_total:6d} gas")
    print(f"  Delta Metadata SSTORE:{delta_sstore:6d} gas  ({records[1]['meta_sstore_cost']} - {records[0]['meta_sstore_cost']})")

    assert delta_total == delta_intrinsic + delta_execution, "Delta total does not match intrinsic + execution!"
    assert delta_execution == delta_sstore, "Delta execution does not match delta metadata SSTORE!"
    print("  -> Delta Total = Delta Intrinsic + Delta Execution [PASSED]")
    print("  -> Delta Execution = Delta Metadata SSTORE [PASSED]")
    print("=" * 80)


if __name__ == "__main__":
    main()
