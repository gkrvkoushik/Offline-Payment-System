# Metric and Invariant Audit: Mathematical Rigour & Codebase Conformance

**Project:** Hybrid Offline Payment with Payer-Liable Settlement and Blockchain-Based Audit Anchoring  
**Scope:** Mathematical Formulations, Integer Paise Precision, Economic Definitions, and Invariant Verification  
**Audit Date:** November 9, 2026  
**Auditor Classification:** Independent Quantitative & Code-Level Audit  
**Status:** FULLY VERIFIED & MATHEMATICALLY RECONCILED

---

## 1. Mathematical Definitions and Code Conformance

| Metric Name | Mathematical Definition | Code Implementation Location | Verified Behavior | Discrepancy / Audit Finding |
| :--- | :--- | :--- | :--- | :---: |
| **Honest Merchant Recovery ($HR$)** | $HR = \frac{\sum_{i \in \mathcal{H}} p_i}{\sum_{i \in \mathcal{H}} c_i}$ | [`adversarial_metrics.py:210`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/metrics/adversarial_metrics.py#L210)<br>[`recovery.py:40`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/metrics/recovery.py#L40) | Returns float in $[0.0, 1.0]$. When eligible honest claims $= 0$, returns `None` (`"N/A"` in CSV). | **NO DISCREPANCY** |
| **Attacker Net Economic Profit ($\Pi_A$)** | $\Pi_A = (G_A + R_{\text{mule}}) - (D_{\text{payer}} + C_{\text{attack}})$ | [`attacker_profit.py:68`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/metrics/attacker_profit.py#L68)<br>[`adversarial_metrics.py:202`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/metrics/adversarial_metrics.py#L202) | Evaluated strictly in integer paise. $G_A$ tracks honest claims where goods were surrendered; $R_{\text{mule}} = P_{\text{mule}} - F_{\text{frozen}}$. | **NO DISCREPANCY** (Unified post-correction) |
| **Reserve Utilization ($RU$)** | $RU = \frac{\sum_{i=1}^m p_i}{S}$ | [`adversarial_metrics.py:216`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/metrics/adversarial_metrics.py#L216) | Total payout divided by available reserve $S$. Returns `None` if $S = 0$. | **NO DISCREPANCY** |
| **Stranded Reserve ($SR$)** | $SR = \begin{cases} S - \sum p_i, & \text{if } U > 0 \\ 0, & \text{if } U = 0 \end{cases}$ | [`adversarial_metrics.py:208`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/metrics/adversarial_metrics.py#L208) | Reserve remaining unspent despite the presence of unpaid eligible claims ($U > 0$). Strictly integer paise. | **NO DISCREPANCY** |
| **System Shortfall** | $\text{Shortfall} = \sum_{i=1}^m c_i - \sum_{i=1}^m p_i$ | [`adversarial_metrics.py:206`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/metrics/adversarial_metrics.py#L206) | Difference between total eligible claim value and settled payout. Integer paise. | **NO DISCREPANCY** |
| **Order Sensitivity ($OS$)** | $OS(M) = \max_{\pi \in \Pi}(M_\pi) - \min_{\pi \in \Pi}(M_\pi)$ | [`adversarial_evaluation.py:205`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/experiments/adversarial_evaluation.py#L205) | Spread of metric $M$ across arrival permutations $\Pi$. | **NO DISCREPANCY** |
| **Payer Collateral Debit ($D_{\text{payer}}$)** | $D_{\text{payer}} = F_C + F_H$ | [`attacker_profit.py:104`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/metrics/attacker_profit.py#L104) | Funds drawn from payer-pledged balances ($C + H$). $F_F$ is excluded. Zero for victim accounts. | **NO DISCREPANCY** |
| **Issuer Guarantee Expenditure ($F_F$)** | $F_F = \min(P_{\text{total}} - F_C - F_H, F)$ | [`base.py:105`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/settlement/base.py#L105)<br>[`telemetry.py:240`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/metrics/telemetry.py#L240) | Backstop expenditure funded by issuing institution. Never debited from payer. | **NO DISCREPANCY** |
| **Frozen Mule Proceeds ($F_{\text{frozen}}$)** | $0 \le F_{\text{frozen}} \le P_{\text{mule}}$ | [`attacker_profit.py:94`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/metrics/attacker_profit.py#L94) | Held or clawed-back mule payouts. Validated with `ValueError` if negative or exceeds $P_{\text{mule}}$. | **NO DISCREPANCY** |

---

## 2. Deep-Dive Mathematical Audit & Protocol Rules

### 2.1 Integer Paise Accounting
All balance, claim, payout, debit, and fee attributes are stored and calculated as Python `int` representing paise ($\text{₹}1.00 = 100 \text{ paise}$).
- **Enforcement:**
  - `Claim.__post_init__` validates `isinstance(self.amount, int) and self.amount > 0`.
  - `Allowance.__post_init__` validates non-negative integers for `allowance_amount`, `payer_hold`, and `issuer_guarantee`.
  - All settlement engines perform integer division (`//`) and largest-remainder distribution using integer moduli. No floating-point rounding is used in financial settlement.

### 2.2 Unified POS Goods Acquisition Qualification
A claim represents physical goods/services acquired at POS if and only if all five conditions are satisfied:
$$\text{GoodsAcquired}(c) \iff \text{offline\_accepted} \land \text{pos\_validation\_passed} \land \text{goods\_released} \land \text{crypto\_valid} \land \text{centre\_valid} \land \neg \text{is\_mule}(c)$$
- **Code Locations:**
  - Method: [`Claim.qualifies_for_goods_acquired()`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/models/claim.py#L50-L75)
  - Helper: [`is_claim_goods_acquired()`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/metrics/attacker_profit.py#L10-L25)
  - Used in: [`attacker_profit.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/metrics/attacker_profit.py#L92), [`telemetry.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/metrics/telemetry.py#L232), and [`adversarial_metrics.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/metrics/adversarial_metrics.py#L191).
- **Test Coverage:** Verified by 6 independent unit test cases in `test_adversarial_evaluation.py::test_pos_goods_release_accounting_independent_cases`.

### 2.3 Segregation of Victim and Malicious Payer Scenarios
When an attacker exploits a cloned credential belonging to an innocent victim:
- The victim’s deposit bears the debit ($D_{\text{victim}} = F_C + F_H$).
- The attacker incurs $D_{\text{payer}} = 0$.
- Consequently, $\Pi_A = (G_A + R_{\text{mule}}) - C_{\text{attack}}$.
When the attacker owns the payer account:
- The attacker incurs $D_{\text{payer}} = F_C + F_H$.
- Consequently, $\Pi_A = (G_A + R_{\text{mule}}) - (F_C + F_H + C_{\text{attack}})$.
- Verified in `test_malicious_payer_vs_compromised_victim_liability`.

### 2.4 Non-Overdraft Waterfall Invariant ($C \to H \to F$)
In [`SettlementBatchResult.compute_funding_sources`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/settlement/base.py#L85-L120):
$$F_C = \min(P, C), \quad F_H = \min(P - F_C, H), \quad F_F = \min(P - F_C - F_H, F)$$
Guarantees:
1. $F_C \le C$, $F_H \le H$, $F_F \le F$.
2. $F_C + F_H + F_F \equiv P$.
3. If $P \le C$, $F_H = 0$ and $F_F = 0$.
4. Tested in `test_invariants.py::test_invariant_10_no_funding_source_overdrawn`.

---

## 3. Audit Findings & Resolution Status

| Item | Prior Status | Current Audit Finding | Resolution |
| :--- | :--- | :--- | :---: |
| **Attacker Profit vs Payout** | Conflated in early drafts | Gross payout strictly distinguished from net profit. | **RESOLVED** |
| **POS Goods Valuation** | Partial checks | Unified across models, metrics, and telemetry via `Claim.qualifies_for_goods_acquired`. | **RESOLVED** |
| **Zero Denominators** | Risk of `0.0` or `1.0` | Returns `None` internally, serialized as `"N/A"` in CSV. | **RESOLVED** |
| **Mule Bounds** | Unbounded frozen funds | Bound checked ($0 \le F_{\text{frozen}} \le P_{\text{mule}}$); raises `ValueError`. | **RESOLVED** |
| **CSV Reconciliation** | Truncating `zip()` | Replaced with strict row/column length checks and literal string equality. | **RESOLVED** |
