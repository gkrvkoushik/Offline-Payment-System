# Invariant Verification: Hybrid Offline Payment Simulator

**Project:** Hybrid Offline Payment with Payer-Liable Settlement and Blockchain-Based Audit Anchoring  
**Scope:** Settlement Policy Invariants, Accounting Rules, and State Transitions  
**Verification Date:** November 9, 2026  
**Status:** FULLY VERIFIED (12/12 Invariants Confirmed by Automated Tests)

---

## 1. Overview of Protocol Invariants

The simulator implements three settlement policies:
- **First Claim Wins (FC):** Single-permit gatekeeper policy where only the first valid claim is honored.
- **Global Pro-Rata (PR):** Reserve-conserving proportional allocation with deterministic integer-paise remainder distribution.
- **Payer-Liable Strict Prefix (PL):** Ingestion-order sequential settlement that pays full claims until the reserve is exhausted, halting on the first claim that cannot be fully satisfied.

Every policy must adhere to mathematical, financial, and state invariants to ensure system safety and economic correctness.

---

## 2. Invariant Audit Matrix

| Invariant ID | Formal Specification | Affected Policies | Enforcing Code Location | Verification Test | Status |
| :---: | :--- | :---: | :--- | :--- | :---: |
| **INV-01** | Total payout cannot exceed total available reserve: $\sum p_i \le S = C + H + F$ | FC, PR, PL | [`base.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/settlement/base.py) | `test_invariant_1_total_payout_never_exceeds_total_reserve` | **VERIFIED** |
| **INV-02** | No claim receives a negative payout: $p_i \ge 0, \forall i$ | FC, PR, PL | [`base.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/settlement/base.py) | `test_invariant_2_no_claim_receives_negative_payout` | **VERIFIED** |
| **INV-03** | No claim receives more than requested face value: $p_i \le c_i, \forall i$ | FC, PR, PL | [`first_claim.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/settlement/first_claim.py), [`pro_rata.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/settlement/pro_rata.py), [`payer_liability.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/settlement/payer_liability.py) | `test_invariant_3_no_claim_receives_more_than_requested` | **VERIFIED** |
| **INV-04** | FC honors at most one claim per permit ID: $\|\{c_i \mid \text{permit}(c_i) = P \land p_i > 0\}\| \le 1$ | FC only | [`first_claim.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/settlement/first_claim.py#L35-L60) | `test_invariant_4_fc_pays_at_most_one_claim_per_permit` | **VERIFIED** |
| **INV-05** | Global PR allocates reserve proportionally to claim weights: $p_i = \lfloor R \times \frac{c_i}{\sum c_m} \rfloor + r_i$, where $\sum r_i = R - \sum \lfloor \dots \rfloor$ | PR only | [`pro_rata.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/settlement/pro_rata.py#L40-L80) | `test_invariant_5_pr_distributes_proportionally_with_integer_rounding` | **VERIFIED** |
| **INV-06** | PL executes strict prefix settlement: $p_i = c_i$ if $\sum_{j=1}^i c_j \le S$; else $p_i = 0$ and all subsequent $p_k = 0$ | PL only | [`payer_liability.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/settlement/payer_liability.py#L30-L75) | `test_invariant_6_pl_follows_strict_ingestion_order_prefix` | **VERIFIED** |
| **INV-07** | Structurally or cryptographically invalid claims never consume reserve: $\neg \text{valid}(c_i) \implies p_i = 0$ | FC, PR, PL | [`base.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/settlement/base.py) | `test_invariant_7_invalid_claims_never_consume_reserve` | **VERIFIED** |
| **INV-08** | Exact UUID replays never generate duplicate payouts | FC, PR, PL | [`base.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/settlement/base.py) | `test_invariant_8_exact_uuid_replays_never_duplicate` | **VERIFIED** |
| **INV-09** | Conflicting UUID payloads are detected and rejected | FC, PR, PL | [`base.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/settlement/base.py) | `test_invariant_9_conflicting_uuid_payloads_rejected` | **VERIFIED** |
| **INV-10** | Funding sources waterfall strictly respects balances: $F_C \le C, F_H \le H, F_F \le F$, and $F_C + F_H + F_F = \sum p_i$ | FC, PR, PL | [`base.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/settlement/base.py#L85-L120) | `test_invariant_10_no_funding_source_overdrawn` | **VERIFIED** |
| **INV-11** | An honest payer with total claims $\le C$ and unique permits receives $100\%$ full settlement | FC, PR, PL | Settlement engines | `test_invariant_11_honest_payer_within_c_receives_full_settlement` | **VERIFIED** |
| **INV-12** | All monetary state variables, payouts, and debits are strictly non-negative integers (paise) | FC, PR, PL | All models & engines | `test_invariant_12_all_calculations_remain_integer_paise` | **VERIFIED** |

---

## 3. Deep-Dive Invariant Proofs

### 3.1 Invariant 1 & 10: Reserve Conservation & Tiered Waterfall
The total available reserve is defined as:
$$S = C + H + F$$
During settlement, payouts are drawn sequentially:
1. First drawn from payer collateral $C$: $F_C = \min(P_{\text{total}}, C)$.
2. Next drawn from payer hold $H$: $F_H = \min(P_{\text{total}} - F_C, H)$.
3. Finally drawn from issuer guarantee $F$: $F_F = \min(P_{\text{total}} - F_C - F_H, F)$.

Because each tier is bounded by its remaining capacity, the total payout satisfies:
$$P_{\text{total}} = F_C + F_H + F_F \le C + H + F = S$$
Remaining reserve is non-negative:
$$R_{\text{rem}} = S - P_{\text{total}} \ge 0$$
Both conditions are enforced in `SettlementBatchResult` post-conditions and verified across all tests.

### 3.2 Invariant 4: First Claim Wins Single-Permit Gate
In [`FirstClaimSettlement`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/settlement/first_claim.py), a set `seen_permits` tracks honored permits:
```python
if claim.permit_id in seen_permits:
    claim_result.status = SettlementStatus.REJECTED
    claim_result.rejection_reason = "Duplicate permit claim (First-Claim wins)"
    claim_result.paid_amount = 0
```
This guarantees that for any permit $P$, exactly one claim can pass validation and receive non-zero payout. Subsequent claims referencing $P$ are rejected regardless of available reserve.

### 3.3 Invariant 5: Global Pro-Rata Proportional Integer Allocation
In [`GlobalProRataSettlement`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/settlement/pro_rata.py), when total eligible claim value $E > S$:
1. Floor allocation: $p_i^{(0)} = \lfloor S \times \frac{c_i}{E} \rfloor$.
2. Remainder: $\Delta = S - \sum_{i=1}^m p_i^{(0)}$.
3. Remainder distribution: The integer remainder $\Delta$ (where $\Delta < m$) is distributed 1 paise at a time to claims sorted deterministically by fractional descending order, breaking ties by `tx_uuid`.
4. Mathematical identity: $\sum_{i=1}^m p_i \equiv S$.

Zero reserve is left stranded ($R_{\text{stranded}} = 0$) when $E \ge S$.

### 3.4 Invariant 6: Payer-Liable Strict Prefix Halting
In [`PayerLiabilitySettlement`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/settlement/payer_liability.py), claims are inspected in arrival order:
```python
if claim.requested_amount <= remaining_reserve:
    # Settle claim in full
    remaining_reserve -= claim.requested_amount
else:
    # Insufficient reserve for complete settlement: HALT
    halted = True
```
Once `halted` becomes `True`:
- The current claim receives $0$ payout (`SettlementStatus.UNPAID`).
- All subsequent claims in the queue receive $0$ payout (`SettlementStatus.UNPAID`), even if a later claim has a smaller face value that would fit within `remaining_reserve`.
- Partial payouts are strictly forbidden in PL.

---

## 4. Attacker Economic Payoff Invariants

1. **Separation of Payout and Profit:**
   $$\Pi = (G + R_{\text{mule}}) - (D_{\text{payer}} + C_{\text{attack}})$$
2. **Goods Surrender Condition:**
   Goods value $G$ increments if and only if:
   `cr.claim.offline_accepted == True` AND `cr.validation_passed == True` AND `cr.claim.is_cryptographically_valid == True` AND `not cr.claim.attacker_controls_payee`.
3. **Payer Debit Liability Attribution:**
   `payer_owned_debit` is strictly drawn from $F_C + F_H$. The institutional guarantee $F_F$ is excluded from payer liability. When `payer_is_attacker == False`, `payer_owned_debit = 0`.
4. **No Double-Counting Assertion:**
   Tested in `test_attacker_profit_explicit_components_and_no_double_counting`: changing the freeze rate $F_{\text{frozen}}$ modifies $R_{\text{mule}}$ and $F_{\text{frozen}}$ inversely while keeping total mule allocation $P_{\text{mule}}$ strictly conserved.

---

## 5. Verification Conclusion

All 12 settlement invariants and all 4 economic payoff invariants have been verified against the codebase and test suite. The simulator strictly preserves formal protocol semantics without approximations.
