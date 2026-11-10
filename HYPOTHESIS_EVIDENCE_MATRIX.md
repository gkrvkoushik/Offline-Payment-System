# Hypothesis Evidence Matrix: Empirical Status & Limitations

**Project:** Hybrid Offline Payment with Payer-Liable Settlement and Blockchain-Based Audit Anchoring  
**Scope:** Mapping Formal Research Hypotheses (H1–H5) against Empirical Findings, Telemetry Datasets, and Experimental Limitations  
**Audit Date:** November 9, 2026  
**Auditor Classification:** Independent Scientific Methodology Audit  

---

## 1. Executive Hypothesis Summary

| Hypothesis ID | Statement | Current Evidence Status | Primary Supporting Dataset | Missing Experimental Work | Paper Chapter Readiness |
| :---: | :--- | :---: | :--- | :--- | :---: |
| **H1** | Sequential policies (FC, PL) exhibit greater observed order sensitivity in the evaluated configurations than Global PR under common claim eligibility. | **SUPPORTED BY EVALUATED CONFIGURATIONS** | `common_eligibility_summary.csv`<br>`ordering_strategies_summary.csv`<br>`ordering_strategies_cross_regime_sensitivity.csv` | None. Macro arrival regimes fully evaluated in EXP-07. | Ready for Results Section 4.2 |
| **H2** | Increasing reserve-to-claim ratio ($\rho$) generally improves honest merchant recovery (recovery increased monotonically in the tested configurations). | **SUPPORTED BY EVALUATED CONFIGURATIONS** | `reserve_ratio_summary.csv` | None. | Ready for Results Section 4.3 |
| **H3** | Sequential strict-prefix settlement (PL) is more sensitive to claim fragmentation than Global PR, though degradation plateaus rather than dropping to zero. | **SUPPORTED BY EVALUATED CONFIGURATIONS** | `account_splitting_summary.csv` | None. | Ready for Results Section 4.4 |
| **H4** | Permit-level rejection (FC) in shared-permit conflicts increases merchant losses compared to common-eligibility reserve pooling when merchants have already released goods. | **SUPPORTED BY EVALUATED CONFIGURATIONS** | `shared_permit_summary.csv`<br>`common_eligibility_summary.csv` | None. Separate shared-permit and common-eligibility datasets established. | Ready for Results Section 4.1 |
| **H5** | Funding composition shifts financial exposure linearly between payer debit liability and institutional loss, while gross payout remains conditionally invariant under fixed total reserves. | **SUPPORTED BY EVALUATED CONFIGURATIONS** | `funding_source_summary.csv`<br>`funding_source_reconciliation.csv`<br>`funding_source_invariance_report.md` | None. Systematic sweep at constant $S=100,000$ paise completed in EXP-08. | Ready for Results Section 4.5 |

---

## 2. Granular Hypothesis Evaluations

### Hypothesis 1 (H1): Order Sensitivity under Common Eligibility
- **Formal Statement:** *Sequential settlement policies (First Claim Wins, Payer-Liable Strict Prefix) exhibit greater observed order sensitivity in honest merchant recovery than Global Pro-Rata when presented with identical eligible claims under scarce reserves across the evaluated arrival regimes.*
- **Supporting Experiments:**
  - EXP-01: Common Eligibility Comparison ([`results/adversarial_evaluation/common_eligibility_summary.csv`](file:///e:/projects/Final-Year/OfflinePayment/version1/results/adversarial_evaluation/common_eligibility_summary.csv))
  - EXP-05: Small Mule Analytical Enumeration ([`results/adversarial_evaluation/small_mule_analytical_reconciliation.csv`](file:///e:/projects/Final-Year/OfflinePayment/version1/results/adversarial_evaluation/small_mule_analytical_reconciliation.csv))
  - EXP-07: Macro Claim-Ordering Strategies ([`results/adversarial_evaluation/exp07_ordering_strategies/ordering_strategies_summary.csv`](file:///e:/projects/Final-Year/OfflinePayment/version1/results/adversarial_evaluation/exp07_ordering_strategies/ordering_strategies_summary.csv))
  - EXP-07: Cross-Regime Sensitivity ([`results/adversarial_evaluation/exp07_ordering_strategies/ordering_strategies_cross_regime_sensitivity.csv`](file:///e:/projects/Final-Year/OfflinePayment/version1/results/adversarial_evaluation/exp07_ordering_strategies/ordering_strategies_cross_regime_sensitivity.csv))
  - EXP-07: Sequence Audit Log ([`results/adversarial_evaluation/exp07_ordering_strategies/ordering_strategies_order_sequences.csv`](file:///e:/projects/Final-Year/OfflinePayment/version1/results/adversarial_evaluation/exp07_ordering_strategies/ordering_strategies_order_sequences.csv))
- **Key Empirical Evidence:**
  - **Global PR is Order-Invariant across all scales and regimes:** In EXP-01 ($N=3$), honest recovery is $66.67\%$ with order sensitivity $\Delta \le 0.000010$. In EXP-07 ($N=10, 50, 100$), honest recovery across all 5 distinct regimes (`GENUINE_FIFO`, `INTERLEAVED_FIFO`, `RANDOM`, `MULE_FIRST`, `HONEST_FIRST`) is strictly $50.000000\%$ with across-regime order sensitivity $OS_{\text{across}} = 0.000000$ and zero within-regime standard deviation ($0.000000$).
  - **FC and PL exhibit extreme across-regime sensitivity:** Under `MULE_FIRST` front-running, honest recovery drops to strictly $0.000000$ (100% loss). Under `HONEST_FIRST`, honest recovery reaches strictly $1.000000$. The across-regime order sensitivity is strictly $1.000000$ (100 percentage points).
  - **Distinctness of Genuine FIFO:** Following corrected population design, `GENUINE_FIFO` is established via a neutral deterministic arrival sequence (seed $42 + N$) where mule and honest claims arrive interspersed independently of claimant category. In `GENUINE_FIFO`, sequential policies achieve honest recovery rates of $60.00\%$ ($N=10$), $44.00\%$ ($N=50$), and $52.00\%$ ($N=100$). It is strictly distinct from `MULE_FIRST` ($0.00\%$), `HONEST_FIRST` ($100.00\%$), and `INTERLEAVED_FIFO` ($40.00\%$ to $50.00\%$) in both actual ordered transaction IDs and claimant categories.
  - **Within-Regime Variability vs. Across-Regime Sensitivity:** Deterministic regimes (`GENUINE_FIFO`, `INTERLEAVED_FIFO`, `MULE_FIRST`, `HONEST_FIRST`) yield zero within-regime sample standard deviation ($0.000000$). The stochastic `RANDOM` regime exhibits within-regime order sensitivity up to $0.600000$ ($N=10$), $0.280000$ ($N=50$), and $0.140000$ ($N=100$).
- **Testability Status:** **TESTABLE & SUPPORTED BY EVALUATED CONFIGURATIONS**.
- **Experimental Limitations:**
  - Front-running (`MULE_FIRST`) and protective ingestion (`HONEST_FIRST`) represent theoretical bounding extremes of network latency and ingestion control, not guaranteed operational real-time outcomes.

---

### Hypothesis 2 (H2): Reserve Availability and Recovery
- **Formal Statement:** *Increasing the reserve-to-claim ratio ($\rho = S / X$) generally improves honest merchant recovery (recovery increased monotonically in the tested configurations) across all settlement policies, while eliminating stranded reserve under Global Pro-Rata.*
- **Supporting Experiments:**
  - EXP-03: Reserve-Ratio Sensitivity ([`results/adversarial_evaluation/reserve_ratio_summary.csv`](file:///e:/projects/Final-Year/OfflinePayment/version1/results/adversarial_evaluation/reserve_ratio_summary.csv))
  - Baseline Coverage Sweep ([`results/reserve_coverage_summary.csv`](file:///e:/projects/Final-Year/OfflinePayment/version1/results/reserve_coverage_summary.csv))
- **Key Empirical Evidence:**
  - Recovery increased strictly monotonically across the tested configurations: $\rho = 0.25 \implies 25.00\%$, $\rho = 0.50 \implies 50.00\%$, $\rho = 0.75 \implies 75.00\%$, and $\rho \ge 1.00 \implies 100.00\%$ across all policies under symmetric claims.
  - Under PR, stranded reserve is strictly $0$ paise whenever claims exceed reserve ($\rho \le 1.00$).
- **Testability Status:** **TESTABLE & SUPPORTED BY EVALUATED CONFIGURATIONS** across 500 paired simulation runs over 5 ratios.
- **Experimental Limitations:**
  - Ratios were tested under uniform honest claim sizes (₹500). Heterogeneous claim distributions at low reserve ratios are evaluated in EXP-05.

---

### Hypothesis 3 (H3): Account Fragmentation Vulnerability
- **Formal Statement:** *Global Pro-Rata is invariant to claim fragmentation (account splitting) under fixed aggregate claim value, whereas sequential strict-prefix settlement (PL) suffers degraded honest recovery as attacker mule claims are split into smaller chunks, though the degradation reaches a non-asymptotic plateau.*
- **Supporting Experiments:**
  - EXP-06: Account Splitting Experiment ([`results/adversarial_evaluation/account_splitting_summary.csv`](file:///e:/projects/Final-Year/OfflinePayment/version1/results/adversarial_evaluation/account_splitting_summary.csv))
- **Key Empirical Evidence:**
  - **Global PR Invariance:** For $k \in \{1, 2, 5, 10\}$ mule accounts, aggregate mule payout is $33,333.33 \pm 1$ paise, and honest recovery is strictly $66.67\%$. Order sensitivity is $\le 2$ paise (strictly bounded by integer remainder ties).
  - **Distinction Between Concepts:** Account splitting (dividing an identity across multiple mule accounts) and claim fragmentation (breaking one large claim into smaller permit claims) confer an ordering advantage in PL because smaller claims fit into residual reserves ahead of larger honest claims.
  - **Non-Asymptotic Degradation Limit:** For $k=1$, PL honest recovery is $66.67\%$. For $k=2$, recovery drops to $58.33\%$. For $k=5$, recovery drops to $51.00\%$. For $k=10$, recovery plateaus at $50.80\%$ rather than dropping to zero, as the finite honest claim sizes still secure residual payouts in favorable arrival positions.
- **Testability Status:** **TESTABLE & SUPPORTED BY EVALUATED CONFIGURATIONS**.
- **Experimental Limitations:**
  - Aggregate mule value was held constant at ₹500 against two ₹500 honest claims. Fragmentation beyond $k=10$ is bounded by transaction fees and minimum offline transaction limits.

---

### Hypothesis 4 (H4): Permit-Level Rejection Impact
- **Formal Statement:** *When merchants have already released physical goods upon offline signature verification, permit-level rejection of conflicting claims (as in First Claim Wins) increases honest merchant losses compared to common-eligibility reserve pooling policies that allocate available reserves across all valid claims.*
- **Supporting Experiments:**
  - EXP-02: Shared-Permit Conflict Comparison ([`results/adversarial_evaluation/shared_permit_summary.csv`](file:///e:/projects/Final-Year/OfflinePayment/version1/results/adversarial_evaluation/shared_permit_summary.csv))
  - EXP-01: Common Eligibility Comparison ([`results/adversarial_evaluation/common_eligibility_summary.csv`](file:///e:/projects/Final-Year/OfflinePayment/version1/results/adversarial_evaluation/common_eligibility_summary.csv))
- **Key Empirical Evidence:**
  - **Shared-Permit Conflict (EXP-02):** In FC, duplicate permit presentation causes 2 out of 3 claims to be rejected at the gate (`rejected_claims_count = 2.0`). If the mule claim arrives first, honest recovery is $0.00\%$; if an honest claim arrives first, the other honest claim is rejected, capping recovery at $50.00\%$ (mean $33.33\%$).
  - **Common-Eligibility Comparison (EXP-01):** When permits are distinct but reserves are scarce, FC does not reject claims at the gate (`rejected_claims_count = 0.0`), yielding a higher mean honest recovery of $50.00\%$.
  - In contrast, Global PR achieves $66.67\%$ honest recovery across both shared-permit and common-eligibility experiments because it distributes reserve across all cryptographically valid presented claims.
- **Testability Status:** **TESTABLE & SUPPORTED BY EVALUATED CONFIGURATIONS**.
- **Experimental Limitations:**
  - Assumes offline acceptance criteria (`pos_validation_passed == True` and `goods_released == True`) occurred prior to batch ingestion at the clearinghouse.

---

### Hypothesis 5 (H5): Funding Composition and Exposure Distribution
- **Formal Statement:** *Varying the proportional composition of payer collateral ($C$), payer hold ($H$), and institutional guarantee ($F$) while holding total reserve ($S = C + H + F$) constant shifts financial exposure linearly between payer debit liability and institutional loss, while gross settlement payout remains invariant under fixed claims and total reserves.*
- **Supporting Experiments:**
  - EXP-08: Funding-Source Composition Sensitivity ([`results/adversarial_evaluation/exp08_funding_sensitivity/funding_source_summary.csv`](file:///e:/projects/Final-Year/OfflinePayment/version1/results/adversarial_evaluation/exp08_funding_sensitivity/funding_source_summary.csv))
  - Invariant Reconciliation: [`results/adversarial_evaluation/exp08_funding_sensitivity/funding_source_reconciliation.csv`](file:///e:/projects/Final-Year/OfflinePayment/version1/results/adversarial_evaluation/exp08_funding_sensitivity/funding_source_reconciliation.csv) (594 runs, 100% PASSED)
  - Invariance Report: [`results/adversarial_evaluation/exp08_funding_sensitivity/funding_source_invariance_report.md`](file:///e:/projects/Final-Year/OfflinePayment/version1/results/adversarial_evaluation/exp08_funding_sensitivity/funding_source_invariance_report.md)
- **Key Empirical Evidence:**
  - **Conditional Gross Payout Invariance:** In all 594 runs across all 11 compositions ($C+H+F \equiv 100,000$ paise), gross payout is strictly $P_{\text{total}} = 100,000$ paise ($₹1,000$). Honest recovery is completely unaffected by funding tier mix.
  - **Exact Linear Financial Exposure Transfer:** Payer debit $D_{\text{payer}} = F_C + F_H$ decreases from $100,000$ paise (at $F=0$) to $0$ paise (at $F=100,000$), while issuer guarantee expenditure $F_F$ increases from $0$ to $100,000$ paise ($P_{\text{total}} \equiv D_{\text{payer}} + F_F$).
  - **Attacker Profit Redistribution:** Under `malicious_payer`, attacker net profit increases linearly with slope $\frac{\partial \Pi_A}{\partial F} = +1.0$ as institutional funds replace forfeited payer balances. Under `compromised_victim`, attacker profit is invariant to $F$ because victim debit is not charged to the attacker ($D_{\text{payer}} = 0$).
- **Testability Status:** **TESTABLE & SUPPORTED BY EVALUATED CONFIGURATIONS**.
- **Experimental Limitations:**
  - Payout invariance holds conditionally upon total reserve $S$ and claim demand being held constant. When $S$ varies, payout follows the reserve ratio dynamics of EXP-03.
