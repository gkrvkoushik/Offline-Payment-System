"""Classification constants for blockchain execution environments."""

# 1. Fast in-memory Python simulation for deterministic unit testing
ENV_MOCK_SIMULATED_EVM = "MOCK_SIMULATED_EVM"

# 2. JSON-RPC mock server for testing network failures, timeouts, and faulty RPC responses
ENV_MOCK_FAULT_INJECTION_RPC = "MOCK_FAULT_INJECTION_RPC"

# 3. Genuine local Hardhat EVM development node executing deployed bytecode
ENV_REAL_LOCAL_HARDHAT_EVM = "REAL_LOCAL_HARDHAT_EVM"

# 4. Genuine local Anvil EVM development node executing deployed bytecode
ENV_REAL_LOCAL_ANVIL_EVM = "REAL_LOCAL_ANVIL_EVM"

# 5. Production/Testnet remote EVM JSON-RPC node (Ethereum, Arbitrum, Base, Polygon)
ENV_PRODUCTION_EVM_RPC = "PRODUCTION_EVM_RPC"
