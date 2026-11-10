import json
from eth_abi import decode
from eth_utils import keccak
from web3 import Web3

w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))

TX1_HASH = "0x0a894afefe52ba411778ba8efcd015d6348bce5ce98eb13f6eb91a47f2aeb45b"
TX2_HASH = "0xd69649ebadce043a1ba3a1414c6292692aa2f4741c956df9e63c8c5f2d2e8d69"

with open("blockchain/build/PaymentAuditAnchor.json") as f:
    artifact = json.load(f)
abi = artifact["abi"]

contract_dummy = w3.eth.contract(abi=abi)

print("=" * 80)
print("AUDIT OF ACTUAL TRANSACTIONS DIRECTLY FROM HARDHAT NODE")
print("=" * 80)

for tx_hash, label in [(TX1_HASH, "Tx 1 (Zero Metadata)"), (TX2_HASH, "Tx 2 (Non-Zero Metadata)")]:
    print(f"\n--- {label} ---")
    tx = w3.eth.get_transaction(tx_hash)
    rcpt = w3.eth.get_transaction_receipt(tx_hash)

    print(f"Transaction Hash: {tx_hash}")
    print(f"Block Number:     {tx['blockNumber']}")
    print(f"Tx Index in Blk:  {tx['transactionIndex']}")
    print(f"From (Sender):    {tx['from']}")
    print(f"To (Contract):    {tx['to']}")
    print(f"Gas Limit:        {tx['gas']}")
    print(f"Gas Price:        {tx['gasPrice']}")
    print(f"Nonce:            {tx['nonce']}")
    print(f"Type:             {tx['type']}")
    print(f"Receipt Status:   {rcpt['status']}")
    print(f"Receipt Gas Used: {rcpt['gasUsed']}")

    # Check input calldata
    raw_input = bytes(tx["input"])
    print(f"Calldata length:  {len(raw_input)} bytes")
    print(f"Raw Input (hex):  {raw_input.hex()}")
    selector = raw_input[:4].hex()
    print(f"Function Selector: 0x{selector}")
    func, params = contract_dummy.decode_function_input(tx["input"])
    print(f"Decoded Function:  {func.fn_name}")
    print(f"Decoded Params:    {params}")

    batch_id_raw = params["batchId"]
    print(f"batchId (bytes):   {batch_id_raw}")
    print(f"batchId (hex):     0x{batch_id_raw.hex()}")
    # ASCII text if printable
    try:
        batch_id_text = batch_id_raw.decode("ascii").rstrip("\x00")
        print(f"batchId (ASCII):   '{batch_id_text}'")
    except Exception:
        pass

    # Verify logs
    print(f"Logs Count:        {len(rcpt['logs'])}")
    if rcpt['logs']:
        log = rcpt['logs'][0]
        print(f"Log Address:       {log['address']}")
        for i, top in enumerate(log['topics']):
            print(f"  Topic[{i}]:        0x{top.hex()}")
        print(f"Log Data (hex):    0x{log['data'].hex()}")
        print(f"Log Data Length:   {len(log['data'])} bytes")

        # Decode log data
        # non-indexed params: uint64 blockTimestamp, uint32 schemaVersion, bytes32 metadataHash
        decoded_data = decode(["uint64", "uint32", "bytes32"], bytes(log["data"]))
        print(f"Decoded Data:      blockTimestamp={decoded_data[0]}, schemaVersion={decoded_data[1]}, metadataHash=0x{decoded_data[2].hex()}")

# Runtime bytecode at target address
target_addr = w3.eth.get_transaction(TX1_HASH)["to"]
deployed_code = w3.eth.get_code(target_addr)
print("\n" + "=" * 80)
print(f"TARGET CONTRACT VERIFICATION AT {target_addr}:")
print(f"Deployed Runtime Code Length: {len(deployed_code)} bytes")
print(f"Deployed Runtime Code SHA-256: {Web3.to_hex(w3.keccak(deployed_code))}")
with open("blockchain/build/PaymentAuditAnchor.json") as f:
    art = json.load(f)
art_bin = bytes.fromhex(art["bytecode"].removeprefix("0x"))
print(f"Artifact Bytecode Length: {len(art_bin)} bytes")

# Trace inspection
print("\n" + "=" * 80)
print("TRACE OPCODES & STEP INDICES:")
for tx_hash, label in [(TX1_HASH, "Tx 1"), (TX2_HASH, "Tx 2")]:
    trace = w3.provider.make_request("debug_traceTransaction", [tx_hash, {}])["result"]
    logs = trace["structLogs"]
    print(f"\n--- {label} ({tx_hash}) - Total StructLogs: {len(logs)} ---")
    for idx, step in enumerate(logs):
        if step["op"] in ("SLOAD", "SSTORE", "LOG4", "LOG3"):
            stack_top = step["stack"][-2:]
            print(f"Step {idx:3d} | PC {step['pc']:3d} | OP: {step['op']:6s} | Cost: {step['gasCost']:5d} | Gas: {step['gas']:6d} | Stack: {stack_top}")
