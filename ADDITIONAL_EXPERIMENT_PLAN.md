# Additional Experiment Plan: Genuinely Missing Experiments

**Project:** Hybrid Offline Payment with Payer-Liable Settlement and Blockchain-Based Audit Anchoring  
**Scope:** Actionable Experimental Protocol for Genuinely Missing Experiments (EXP-07 and EXP-08)  
**Audit Date:** November 9, 2026  
**Auditor Classification:** Research Protocol Design & Planning  

---

## 1. Overview of Genuinely Missing Experiments

Based on the source-level audit, 6 of the 8 experiments (EXP-01 through EXP-06) are fully implemented, verified, and reconciled against published CSV datasets. Only two experiments genuinely require implementation and data generation:

1. **EXP-07 — Claim-Ordering Strategies (FIFO vs. Random vs. Mule-First vs. Honest-First):** Evaluates macro-level arrival order structures across varying claim volumes and reserve shortages to answer **RQ1**.
2. **EXP-08 — Funding-Source Composition Sensitivity ($C:H:F$ Sweep holding $S$ constant):** Evaluates how the ratio of payer collateral, payer hold, and institutional guarantee shifts financial liability between payer and issuer to answer **RQ5**.

Neither experiment requires modifying settlement policies (FC, PR, PL), cryptographic validation rules, or established simulation semantics. Both can be implemented by invoking existing class methods in [`AdversarialEvaluationSuite`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/experiments/adversarial_evaluation.py).

---

## 2. Detailed Protocol: Experiment 7 (EXP-07)

### Claim-Ordering Strategies Across Arrival Regimes

1. **Research Question:** **RQ1** — *How does claim-ingestion order affect honest merchant recovery under limited reserves?*
2. **Hypothesis:** **H1** — *Global PR remains invariant across structured ordering strategies, whereas FC and PL exhibit severe performance divergence between Honest-First and Mule-First arrival scenarios.*
3. **Ingestion Ordering Regimes:**
   - **`FIFO` (Natural Submission Sequence):** Claims sorted strictly by client submission timestamp.
   - **`Random` (Stochastic Ingestion Shuffle):** Uncorrelated queue arrival order (standard network latency model).
   - **`Mule-First` (Attacker Front-Running / Sensitivity Bound):** All attacker-controlled mule claims arrive before honest merchant claims. *(Treated explicitly as a worst-case sensitivity benchmark, not an assumed capability of the attacker).*
   - **`Honest-First` (Protective Clearinghouse Ingestion):** Honest merchant claims arrive before attacker mule claims.
4. **Independent Variables:**
   - Ingestion Strategy: `['FIFO', 'Random', 'Mule_First', 'Honest_First']`
   - Reserve Coverage Ratio: $\rho \in [0.25, 0.50, 0.75, 1.00]$
   - Settlement Policy: `['FIRST_CLAIM', 'GLOBAL_PRO_RATA', 'PAYER_LIABILITY']`
5. **Controlled Variables:**
   - Total Claims: $N = 10$ claims (3 mule claims of ₹500, 7 honest claims of ₹500; Total claimed = ₹5,000 / 500,000 paise).
   - Funding Composition: Standard collateral allocation ($C = 50\%, H = 50\%, F = 0\%$).
   - Permit Structure: Distinct valid permits (pure reserve rationing without permit invalidation).
6. **Dependent Variables:**
   - `honest_recovery_rate` ($HR \in [0.0, 1.0]$)
   - `attacker_net_profit_paise` ($\Pi_A$)
   - `mule_payout_paise` ($P_{\text{mule}}$)
   - `reserve_utilization` ($RU$)
   - `stranded_reserve_paise` ($SR$)
7. **Replication & Seeds:**
   - 50 paired random seeds per parameter combination for the `Random` strategy; deterministic single run per configuration for `FIFO`, `Mule_First`, and `Honest_First`.
8. **Required Output CSV Schemas:**
   - `results/adversarial_evaluation/order_strategies_runs.csv`
   - `results/adversarial_evaluation/order_strategies_summary.csv`
   - Columns: `experiment,ordering_strategy,reserve_ratio,seed,policy,total_eligible_paise,available_reserve_paise,total_payout_paise,honest_eligible_paise,honest_payout_paise,honest_recovery_rate,attacker_payout_paise,attacker_net_profit_paise,reserve_utilization,stranded_reserve_paise`.
9. **Statistical Analysis:**
   - Pairwise paired t-tests or Wilcoxon signed-rank tests between `Honest_First` and `Mule_First` for each policy to quantify sensitivity spread.
10. **Acceptance Criteria:**
    - Global PR recovery spread between `Honest_First` and `Mule_First` must be $\le 0.01\%$ (integer remainder rounding only).
    - PL recovery spread must exceed $20.00\%$ at $\rho \in [0.50, 0.75]$.

---

## 3. Detailed Protocol: Experiment 8 (EXP-08)

### Funding-Source Composition Sensitivity ($C:H:F$ Sweep)

1. **Research Question:** **RQ5** — *How does the composition of payer allowance, payer hold and issuer guarantee affect economic losses?*
2. **Hypothesis:** **H5** — *Holding total funding $S$ constant, shifting composition from collateral ($C + H$) to institutional guarantee ($F$) linearly reduces payer collateral debits and increases institutional exposure, increasing attacker net profit under malicious payer ownership without altering honest merchant recovery.*
3. **Funding Composition Regimes (Constant $S = 100,000$ paise / ₹1,000):**
   - **Config 1 (Collateral-Heavy):** $C = 80,000$ (80%), $H = 20,000$ (20%), $F = 0$ (0%)
   - **Config 2 (Balanced Payer):** $C = 50,000$ (50%), $H = 50,000$ (50%), $F = 0$ (0%)
   - **Config 3 (Tri-Partite Equal):** $C = 33,334$ (33.3%), $H = 33,333$ (33.3%), $F = 33,333$ (33.3%)
   - **Config 4 (Moderate Guarantee):** $C = 40,000$ (40%), $H = 20,000$ (20%), $F = 40,000$ (40%)
   - **Config 5 (Guarantee-Heavy):** $C = 20,000$ (20%), $H = 10,000$ (10%), $F = 70,000$ (70%)
   - **Config 6 (Full Guarantee):** $C = 0$ (0%), $H = 0$ (0%), $F = 100,000$ (100%)
4. **Independent Variables:**
   - Funding Configuration: Configs 1 through 6
   - Payer Liability Scenario: `['malicious_payer', 'compromised_victim']`
   - Settlement Policy: `['FIRST_CLAIM', 'GLOBAL_PRO_RATA', 'PAYER_LIABILITY']`
5. **Controlled Variables:**
   - Total Reserve: $S = 100,000$ paise (₹1,000)
   - Total Claims: 3 claims of ₹500 each (1 mule, 2 honest; Total claimed = ₹1,500 / 150,000 paise)
   - Claim Arrival Order: Ingestion sequence fixed or exhaustively averaged across all 6 permutations.
6. **Dependent Variables:**
   - Payer Collateral Debit ($D_{\text{payer}} = F_C + F_H$)
   - Issuer Guarantee Expenditure ($F_F$)
   - Honest Merchant Recovery ($HR$)
   - Attacker Net Economic Profit ($\Pi_A = G + R_{\text{mule}} - D_{\text{payer}} - C_{\text{attack}}$)
7. **Replication & Permutations:**
   - All 6 arrival permutations evaluated per configuration $\times$ 2 payer ownership models = 72 runs per policy (216 runs total).
8. **Required Output CSV Schemas:**
   - `results/adversarial_evaluation/funding_source_runs.csv`
   - `results/adversarial_evaluation/funding_source_summary.csv`
   - Columns: `experiment,config_name,pct_c,pct_h,pct_f,payer_ownership,policy,total_reserve_paise,funded_from_c,funded_from_h,funded_from_f,payer_owned_debit_paise,issuer_expenditure_paise,honest_recovery_rate,attacker_net_profit_paise`.
9. **Statistical Analysis:**
   - Linear regression of $D_{\text{payer}}$ and $\Pi_A$ against $F\%$ to verify exact slope $\frac{\partial \Pi_A}{\partial F} = +1.0$ under malicious payer ownership.
10. **Acceptance Criteria:**
    - For all policies, `honest_recovery_rate` must remain strictly identical across all 6 funding configurations (since total $S$ is constant).
    - $D_{\text{payer}} + F_F$ must strictly equal total settled payout $P_{\text{total}}$ in every single run.
    - Issuer expenditure $F_F$ must equal $\max(0, P_{\text{total}} - C - H)$.

---

## 4. Implementation Readiness & Risk Assessment

Both proposed experiment suites require **no architectural changes**. The necessary methods and data models already exist in:
- [`src/offline_payment/models/allowance.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/models/allowance.py)
- [`src/offline_payment/settlement/base.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/settlement/base.py)
- [`src/offline_payment/attacks/claim_ordering.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/attacks/claim_ordering.py)
- [`src/offline_payment/metrics/attacker_profit.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/metrics/attacker_profit.py)

Adding these two suites will elevate experimental coverage to **100% (8/8 planned experiments)**.
