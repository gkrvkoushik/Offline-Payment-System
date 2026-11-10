# Hybrid Offline Payment Research Simulator

A Python-based discrete research simulator for evaluating settlement policies, double-spending resistance, and blockchain audit anchoring in offline digital payments.

**Research Title:** *Hybrid Offline Payment with Payer-Liable Settlement and Blockchain-Based Audit Anchoring*

---

## 1. Project Objective & Threat Model

In intermittent or fully offline environments, digital payment credentials (permits) can be duplicated or presented to multiple merchants before online settlement occurs (double-spending).

### Core Research Realities & Threat Boundaries
1. **Blockchain Does Not Prevent Offline Double-Spending:**  
   Offline payment acceptance occurs peer-to-peer at the point of sale (POS) between disconnected smartphone devices. Without continuous online connectivity or tamper-resistant secure hardware enclaves, an adversary possessing cryptographic spending credentials can present duplicated permits to multiple honest merchants. Blockchain consensus operates strictly online and **cannot** prevent offline double-spending or cloned credentials at the POS.
2. **Role of Blockchain Audit Anchoring:**  
   The blockchain provides **tamper-evident, non-repudiable public auditability**. It anchors the cryptographic state (domain-separated Merkle roots of ingestion, validation, and settlement batches) to an immutable public or consortium ledger. This prevents dishonest settlement operators from:
   - Secretly altering ingestion sequences to favor certain merchants or mule accounts.
   - Suppressing legitimate merchant claims after the fact.
   - Tampering with pro-rata allocations or modifying collateral utilization records.
   - Fabricating retrospective double-spending allegations against honest payers.
3. **Decoupled Asynchronous Settlement (Offline Resilience):**  
   Offline payment clearing and online settlement **never** block on blockchain transaction confirmations, gas price spikes, or network outages. Settlement decisions remain strictly deterministic off-chain; batch roots are asynchronously enqueued, signed, and anchored to the blockchain with automated retry mechanisms.

---

## 2. Protocol & Architecture Overview

### Funding Waterfall ($S = C + H + F$)
Settlement reserves for an offline payment allowance are backed by three tiers:
- **Payer Commitment ($C$)**: Dedicated offline spending balance pre-locked from the payer's account.
- **Payer Hold ($H$)**: Collateral balance held in reserve to absorb double-spending liability.
- **Issuer Guarantee ($F$)**: Issuer-backed backstop fund guaranteeing merchant settlement.
- **Total Reserve ($S$)**: $S = C + H + F$.

All monetary calculations are performed strictly in **integer paise** (1 INR = 100 paise) to eliminate floating-point drift and rounding errors.

### Settlement Policies

| Policy | Mechanism | Duplicate Permit Handling | Partial Payouts | Reserve Pooling |
|---|---|---|---|---|
| **First Claim Wins (FC)** | Greedily settles the first cryptographically valid claim referencing a permit. | Subsequent claims referencing the same permit are rejected. | Allowed if remaining reserve < claim amount. | Per-permit gate backed by global reserve. |
| **Global Pro-Rata (PR)** | Pools total reserve $S$ and distributes it proportionally across all eligible claims: $p_j = x_j \cdot \min(1, S/X)$. Allocates integer paise via largest-remainder rounding (Hare-Niemeyer). | Permitted; all valid claims pool for reserve share. | Yes (haircuts applied proportionally). | Global across all claims in the settlement batch. |
| **Payer-Liable Strict Prefix (PL)** | Settles cryptographically eligible claims strictly in ascending ingestion sequence via waterfall: $C \to H \to F$. | Permitted; settled in arrival order up to available reserve. | **No** (all-or-nothing). Halts processing if a claim cannot be paid in full. | Strict chronological prefix allocation. |

---

## 3. Blockchain Audit Anchoring Architecture

```text
  [Offline POS]  ─────────> [Claim Submission]
                                   │
                                   ▼
                      [ClaimValidator & Settlement]
                       (FC, PR, or PL Algorithms)
                                   │
                                   ▼
                       [Canonical Audit Events]
                       (RFC 8785 Canonical JSON)
                                   │
                                   ▼
                     [Domain-Separated Merkle Tree]
                     Leaf:     SHA256(0x00 || EventData)
                     Internal: SHA256(0x01 || Left || Right)
                                   │
                         ┌─────────┴─────────┐
                         ▼                   ▼
                 [AnchorQueueManager]  [Inclusion Proofs]
                 (CREATED -> QUEUED ->        │
                  ANCHORED / RETRY)           ▼
                         │          [Independent Verifier]
                         ▼          (Validates Proofs and
             [PaymentAuditAnchor.sol] Conservation of Funds)
             (EVM Smart Contract)
```

### 1. Canonical Serialization (RFC 8785)
- Deterministic key ordering at all nesting depths.
- Compact delimiters (`:`, `,`) with no extraneous whitespace.
- Explicit prohibition of floating-point numbers in financial payloads.
- Normalized UTF-8 encoding.

### 2. Cryptographic Domain Separation
To prevent second-preimage attacks (where an internal node is substituted for a leaf), hashes use explicit prefixes:
$$\text{Leaf Hash} = H(\texttt{0x00} \parallel \text{canonical\_bytes})$$
$$\text{Internal Node Hash} = H(\texttt{0x01} \parallel \text{left\_child} \parallel \text{right\_child})$$
Odd-count levels duplicate the trailing node in accordance with RFC 6962.

### 3. Smart Contract (`blockchain/contracts/PaymentAuditAnchor.sol`)
- Immutably stores `(merkleRoot, submitter, blockTimestamp, metadataHash)` keyed by `bytes32 batchId`.
- Emits `AuditBatchAnchored` events for public indexing.
- Rejects duplicate batch registrations to prevent replay attacks.
- Supports on-chain proof verification via the EVM SHA-256 precompile (`0x02`).

### 4. Independent Audit Verification Service
Allows merchants, regulatory bodies, and external auditors to verify claims without trusting the settlement operator:
- Validates single-claim inclusion proofs against on-chain anchored roots in $O(\log N)$ time.
- Validates full batch audit trails by recomputing the Merkle root from event logs.
- Formally validates **Conservation of Funds**:
  $$\sum \text{Paid} = \sum C_{\text{funded}} + \sum H_{\text{funded}} + \sum F_{\text{funded}} \le S$$
  $$\forall j: 0 \le \text{Paid}_j \le \text{Requested}_j$$
  $$\sum C_{\text{funded}} \le C, \quad \sum H_{\text{funded}} \le H, \quad \sum F_{\text{funded}} \le F$$

---

## 4. Directory Structure

```text
version1/
│
├── blockchain/
│   └── contracts/
│       └── PaymentAuditAnchor.sol     # Solidity contract anchoring Merkle batch roots
│
├── src/
│   └── offline_payment/
│       ├── __init__.py
│       ├── config.py                  # Enums, currency units, status definitions
│       │
│       ├── models/                    # Core domain entities
│       │   ├── __init__.py
│       │   ├── account.py             # Ledger account with balance invariants
│       │   ├── allowance.py           # Three-tier allowance funding model (C, H, F)
│       │   ├── permit.py              # Spending credentials and denominations
│       │   └── claim.py               # Transaction redemption claims (offline acceptance flag)
│       │
│       ├── settlement/                # Independent settlement algorithms
│       │   ├── __init__.py
│       │   ├── base.py                # Base policy interface & batch result models
│       │   ├── first_claim.py         # Policy A: First Claim Wins (FC)
│       │   ├── pro_rata.py            # Policy B: Global Pro-Rata (PR)
│       │   └── payer_liability.py     # Policy C: Payer-Liable Strict Prefix (PL)
│       │
│       ├── validation/                # Pre-settlement checks & replay handling
│       │   ├── __init__.py
│       │   └── claim_validator.py     # Crypto verification & UUID conflict deduplication
│       │
│       ├── attacks/                   # Adversarial scenario generators
│       │   ├── __init__.py
│       │   ├── double_spend.py        # Multi-merchant permit reuse
│       │   ├── self_claim.py          # Attacker self-redemption
│       │   ├── mule_account.py        # Mule account network & deterministic integer rounding
│       │   ├── cloned_key.py          # Compromised credential attacks
│       │   └── claim_ordering.py      # Strategic arrival sequence manipulation
│       │
│       ├── audit/                     # Canonical audit & Merkle anchoring subsystem
│       │   ├── __init__.py
│       │   ├── events.py              # Canonical audit events & payload definitions
│       │   ├── canonicalization.py    # RFC 8785 deterministic serialization
│       │   ├── hashing.py             # Domain-separated SHA-256 (0x00 leaf, 0x01 node)
│       │   ├── merkle_tree.py         # Merkle tree generator & root calculation
│       │   ├── proofs.py              # Inclusion proofs & standalone verification
│       │   ├── audit_service.py       # Settlement audit trail pipeline
│       │   └── verification.py        # Independent audit verification service
│       │
│       ├── blockchain/                # Blockchain adapter and async queue manager
│       │   ├── __init__.py
│       │   ├── adapter.py             # BlockchainAdapter interface & SimulatedEVMAdapter
│       │   └── anchor_service.py      # Asynchronous state machine & retry queue
│       │
│       ├── metrics/                   # Evaluation metrics
│       │   ├── __init__.py
│       │   ├── recovery.py            # Total, honest, and mule recovery rates (None on zero denominator)
│       │   ├── attacker_profit.py     # Adversary economic payoff formulation
│       │   ├── financial_loss.py      # Stakeholder loss accounting
│       │   └── telemetry.py           # Permit inventory, attack events, and anchor ledger logging
│       │
│       ├── experiments/               # Parameter sweep experiment modules
│       │   ├── __init__.py
│       │   ├── policy_comparison.py   # Baseline reproducible experiment
│       │   ├── reserve_coverage.py    # S/X ratio sensitivity sweep
│       │   ├── receiver_sweep.py      # Receiver count, mule share & position sweep
│       │   ├── denomination.py        # Controlled denomination granularity sweep (INR 1,000 invariant)
│       │   ├── multiseed.py           # Reproducible multi-seed randomized simulation
│       │   └── blockchain_performance.py # Merkle tree, proof latency, gas & resilience benchmark
│       │
│       ├── visualization/             # Comparative graph plotting
│       │   ├── __init__.py
│       │   └── plots.py               # Publication-quality matplotlib graphs
│       │
│       └── simulation/                # Simulation orchestration
│           ├── __init__.py
│           └── runner.py              # Experiment orchestration & console reporting
│
├── tests/                             # Pytest test suite (84 automated tests)
│   ├── test_models.py                 # Domain models and balance invariants
│   ├── test_validation.py             # Replay and cryptographic validation
│   ├── test_first_claim.py            # FC policy unit tests
│   ├── test_pro_rata.py               # PR policy unit tests
│   ├── test_payer_liability.py        # PL policy unit tests
│   ├── test_invariants.py             # 12 formal correctness invariants
│   ├── test_attack_scenarios.py       # Attack generators and metrics verification
│   ├── test_regressions.py            # Defect regressions & boundary tests
│   ├── test_denomination.py           # Controlled denomination experiment tests
│   ├── test_deliverables.py           # Permit inventory, attack events, anchors, and graph tests
│   ├── test_audit_events.py           # Canonical serialization & domain-separated hashing
│   ├── test_merkle_tree.py            # Merkle tree math, odd nodes, and inclusion proofs
│   ├── test_blockchain_adapter.py     # Simulated EVM, gas accounting, queue, and retries
│   └── test_audit_verification.py     # End-to-end settlement anchoring and independent verification
│
├── results/                           # Experiment outputs and raw observations
│   ├── initial_experiment.csv
│   ├── reserve_coverage_summary.csv
│   ├── reserve_coverage_raw.csv
│   ├── receiver_sweep_summary.csv
│   ├── receiver_sweep_raw.csv
│   ├── denomination_summary.csv
│   ├── denomination_raw.csv
│   ├── multiseed_summary.csv
│   ├── multiseed_raw.csv
│   ├── blockchain_performance_summary.csv # Merkle and blockchain scaling observations
│   ├── permit_inventory.csv           # Complete issued permit inventory including unused permits
│   ├── attack_events.csv              # Offline POS acceptance, goods released, and attack costs
│   ├── audit_anchors.csv              # Complete blockchain audit anchoring ledger
│   └── graphs/                        # High-resolution comparison charts
│       ├── baseline_comparison.png
│       ├── denomination_granularity_comparison.png
│       ├── receiver_sweep_comparison.png
│       ├── multiseed_distribution.png
│       └── blockchain_performance_scaling.png
│
├── main.py                            # Main simulation runner entry point
├── pyproject.toml                     # Project packaging and test discovery
├── uv.lock                            # Deterministic dependency lockfile
├── .python-version                    # Python 3.12 pin
├── .gitignore
└── README.md
```

---

## 5. Setup and Environment

This project uses [`uv`](https://docs.astral.sh/uv/) for Python environment and dependency management.

### Prerequisites
- Python 3.12+
- `uv` installed on your system

### Installation

```bash
# Sync dependencies (including matplotlib for publication charts)
uv sync --dev
```

---

## 6. Running Tests

Run the test suite verifying all 84 unit, regression, invariant, and integration tests:

```bash
uv run pytest
```

---

## 7. Running Experiments & Generating Deliverables

To execute all experiments, benchmark blockchain audit scaling, regenerate all CSV datasets, and produce comparative graphs:

```bash
uv run python main.py
```

---

## 8. Experimental Methodology & Deliverables

### Deliverable 1: Complete Permit Inventory (`results/permit_inventory.csv`)
Tracks every issued offline permit across all allowances and policies:
- Identifies **unused permits** (`permit_status = 'UNUSED'`, `claims_count = 0`), fully consumed permits (`CONSUMED_FULL`), partially consumed permits (`CONSUMED_PARTIAL`), and double-spent permits (`DOUBLE_SPENT`).
- Reconciles stranded permit reserve: $\text{Stranded Value} = \text{Denomination} - \text{Total Settled}$.

### Deliverable 2: Attack Events & POS Acceptance Telemetry (`results/attack_events.csv`)
Logs point-of-sale dynamics and adversary accounting:
- **Decoupled POS Acceptance**: Records `offline_accepted` (merchant acceptance) vs. `goods_released` (offline goods surrendered).
- **Adversary Payoff**:
  $$\text{Attacker Profit} = \text{Goods Acquired} + \text{Recoverable Mule Credit} - \text{Payer-Owned Debit} - \text{Attack Costs}$$
  - Goods are acquired if and only if `offline_accepted == True`, `validation_passed == True`, and `claim_type == HONEST_MERCHANT`.
  - Recoverable mule credit is strictly tied to settled payout in mule-controlled accounts.
  - Payer-owned debit is $C + H$ consumed; $F$ is never counted as payer debit.

### Deliverable 3: Blockchain Audit Anchoring Ledger (`results/audit_anchors.csv`)
Logs all settlement batches anchored onto the blockchain:
- Records `experiment_name`, `policy`, `batch_id`, `allowance_id`, `event_count`, `merkle_root`, `tx_hash`, `block_number`, `gas_used`, and `status`.

### Deliverable 4: Blockchain Performance & Scaling Benchmarks (`results/blockchain_performance_summary.csv` & `results/evm_gas_reconciliation.csv`)
Empirical benchmarks demonstrating deterministic $O(n)$ Merkle tree construction, sub-millisecond cryptographic operations, and genuine Hardhat EVM transaction execution:

| Leaves ($n$) | Tree Depth | Internal Node Hashes | Build Latency (ms) [95% CI] | Proof Gen Latency (µs) | Proof Verify Latency (µs) | Mined Anchor Latency (ms) | Actual EVM Gas |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **10** | 5 | 11 | 0.18 ms [0.15, 0.21] | 10.5 µs | 9.2 µs | 27.6 ms | 74,330 |
| **50** | 7 | 52 | 0.56 ms [0.46, 0.67] | 10.7 µs | 9.3 µs | 24.4 ms | 74,318 |
| **100** | 8 | 102 | 1.16 ms [0.97, 1.34] | 11.8 µs | 12.6 µs | 22.8 ms | 74,342 |
| **250** | 9 | 251 | 2.64 ms [2.18, 3.10] | 16.8 µs | 13.1 µs | 24.1 ms | 74,342 |
| **500** | 10 | 501 | 6.69 ms [5.67, 7.72] | 20.7 µs | 20.3 µs | 34.3 ms | 74,342 |
| **1,000** | 11 | 1,001 | 10.00 ms [8.74, 11.26] | 16.7 µs | 16.4 µs | 22.5 ms | 74,354 |

- **Exact Merkle Internal Hashing Recurrence:** Under the duplicate-last-node rule for odd levels, tree construction follows the recurrence $L_0 = n, L_{k+1} = \lceil L_k / 2 \rceil$. The exact internal node count is $H(n) = \sum_{k=1}^{\lceil \log_2 n \rceil} L_k$, bounded tightly by $n - 1 \le H(n) < 2n$. Construction time complexity is strictly $O(n)$, while inclusion proof generation and verification are $O(\log n)$.
- **Empirical Gas Audit Across 90 Mined Benchmark Transactions (`PaymentAuditAnchor.sol`):**
  - All 90 transactions succeeded on the Hardhat node (Status `0x1`).
  - Total receipt `gasUsed` strictly spans **74,206 to 74,242 gas** across the 90 benchmark transactions (and up to 74,386 for longer 32-character test identifiers).
  - Intrinsic calldata gas accounts for 21,952 to 21,988 gas ($21,000 + 4 \times \text{zeros} + 16 \times \text{non-zeros}$).
  - Contract execution gas is **invariant at exactly 52,254 gas** across all 90 benchmark transactions.
  - Actual event logging emits `AuditBatchAnchored` using `LOG4` (1 event signature topic + 3 indexed parameter topics = 4 topics, plus 3 non-indexed data fields).
  - Storage writes allocate 3 storage slots per anchor (`_anchors[batchId]`), packing `submitter` (160 bits), `blockTimestamp` (64 bits), and `schemaVersion` (32 bits) into a single 32-byte slot.
  - On-Chain Inclusion Verification: **27,384 gas** for a mined transaction (or **26,720 gas** via `eth_estimateGas`) executing the SHA-256 precompile (`0x02`).
- **Outage Resilience & Queue Crash Recovery:** 100% recovery rate with zero data loss under simulated RPC downtime, ambiguous transaction timeout reconciliation, process restart with pending tasks, and explicit rejection (`FAILED_FINAL`) when queued roots conflict with on-chain anchored records.

### Deliverable 5: Comparative Visualization Graphs (`results/graphs/`)
- `baseline_comparison.png`: Side-by-side payout distributions, honest recovery, and attacker net profit under the baseline double-spending scenario.
- `denomination_granularity_comparison.png`: Shows how Micro (10 × ₹100), Standard (2 × ₹500), and Large (1 × ₹1,000) permits isolate double-spending blast radius under FC, and how PR/PL protect honest recovery across all permit sizes.
- `receiver_sweep_comparison.png`: Evaluates honest recovery and attacker net profit as receiver counts scale from 2 to 20.
- `multiseed_distribution.png`: Error-bar charts showing mean $\pm$ standard deviation across multi-seed runs.
- `blockchain_performance_scaling.png`: Scaling curves for Merkle tree construction latency, proof generation, and verification.

---

## 9. Baseline Reproducible Experiment Results

**Configuration:** $C = \text{₹500}$, $H = \text{₹500}$, $F = \text{₹0}$ $\implies$ Reserve $S = \text{₹1,000}$. 1 permit of ₹500, 3 claims of ₹500 (1 Mule, 2 Honest Merchants).

| Policy | Mule Payout | Merchant A | Merchant B | Total Payout | Honest Recovery | Attacker Net Profit |
|:---|---:|---:|---:|---:|---:|---:|
| **FC** | ₹500.00 | ₹0.00 | ₹0.00 | ₹500.00 | 0.0% | ₹1,000.00 |
| **PR** | ₹333.34 | ₹333.33 | ₹333.33 | ₹1,000.00 | 66.7% | ₹333.34 |
| **PL** | ₹500.00 | ₹500.00 | ₹0.00 | ₹1,000.00 | 50.0% | ₹500.00 |
