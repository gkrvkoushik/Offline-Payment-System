# EXP-07 Reproducibility & Methodological Refinement Report

**Experiment:** EXP-07 Macro Claim-Ordering Strategies Across Arrival Regimes  
**Evaluation Date:** 2026-11-09  
**Methodological Refinement:** Distinction of Genuine FIFO vs Interleaved FIFO; Separation of Within-Regime Variability vs Across-Regime Sensitivity.  

---

## 1. Ordering Strategy Definitions

1. **`GENUINE_FIFO` (Genuine First-In First-Out):**
   - Preserves the exact original claim arrival sequence without sorting or rearranging by claimant category.
   - Populated independently of arrival order, then sequenced via a neutral deterministic arrival process (seed $42 + N$).
   - Intersperses mule and honest claims naturally (e.g., $N=10$ has 2 mules and 3 honest claims in the first half).
   - Distinct from MULE_FIRST, HONEST_FIRST, and INTERLEAVED_FIFO.

2. **`INTERLEAVED_FIFO` (Synthetic Alternating Arrival):**
   - Alternates arrivals between mule and honest claims (`Mule 0, Honest 0, Mule 1, Honest 1, ...`).
   - Represents a benchmark interleaved queue.

3. **`RANDOM` (Stochastic Queue Permutation):**
   - Generates an uncorrelated pseudo-random shuffle of the claim batch using an explicit recorded seed (`70000 + N * 1000 + seed`).
   - The exact same permutation is evaluated across FC, Global PR, and PL for each seed replicate.

4. **`MULE_FIRST` (Adversary Front-Running Sensitivity Bound):**
   - All attacker-controlled mule claims arrive before honest merchant claims.
   - Preserves stable relative ordering within each claimant category.
   - Represents the theoretical worst-case sensitivity benchmark, not an assumed real-world attacker capability.

5. **`HONEST_FIRST` (Protective Clearinghouse Ingestion Bound):**
   - All honest merchant claims arrive before attacker mule claims.
   - Preserves stable relative ordering within each claimant category.
   - Represents the theoretical upper bound of honest merchant protection.

---

## 2. Statistical Separation: Within-Regime Variability vs. Across-Regime Sensitivity

### A. Within-Regime Variability
For deterministic strategies (`GENUINE_FIFO`, `INTERLEAVED_FIFO`, `MULE_FIRST`, `HONEST_FIRST`), identical sequences are evaluated across seeds. Zero variability is explicitly documented as a consequence of the fixed sequence, rather than falsely attributing zero variance to independent stochastic observations.
For `RANDOM`, variability is computed using sample standard deviation (`ddof=1`), 95% confidence intervals, and interquartile range across 30 independent seeds.

### B. Across-Regime Sensitivity ($OS_{\text{across}}$)
Across-regime sensitivity is defined strictly across the 5 regime means for each batch size and policy:
$$OS_{\text{across}}(HR) = \max_{\text{regime}}(\overline{HR}_{\text{regime}}) - \min_{\text{regime}}(\overline{HR}_{\text{regime}})$$ 
$$OS_{\text{across}}(\Pi_A) = \max_{\text{regime}}(\overline{\Pi}_{A,\text{regime}}) - \min_{\text{regime}}(\overline{\Pi}_{A,\text{regime}})$$ 

---

## 3. Empirical Across-Regime Results Summary

| Batch Size ($N$) | Settlement Policy | Min Mean $HR$ | Max Mean $HR$ | Across-Regime $OS(HR)$ | Min Mean $\Pi_A$ (paise) | Max Mean $\Pi_A$ (paise) | Across-Regime $OS(\Pi_A)$ (paise) |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| 10 | FIRST_CLAIM | 0.0000 | 1.0000 | **1.0000** | 0.0 | 250000.0 | **250000.0** |
| 10 | GLOBAL_PRO_RATA | 0.5000 | 0.5000 | **0.0000** | 125000.0 | 125000.0 | **0.0** |
| 10 | PAYER_LIABILITY | 0.0000 | 1.0000 | **1.0000** | 0.0 | 250000.0 | **250000.0** |
| 50 | FIRST_CLAIM | 0.0000 | 1.0000 | **1.0000** | 0.0 | 1250000.0 | **1250000.0** |
| 50 | GLOBAL_PRO_RATA | 0.5000 | 0.5000 | **0.0000** | 625000.0 | 625000.0 | **0.0** |
| 50 | PAYER_LIABILITY | 0.0000 | 1.0000 | **1.0000** | 0.0 | 1250000.0 | **1250000.0** |
| 100 | FIRST_CLAIM | 0.0000 | 1.0000 | **1.0000** | 0.0 | 2500000.0 | **2500000.0** |
| 100 | GLOBAL_PRO_RATA | 0.5000 | 0.5000 | **0.0000** | 1250000.0 | 1250000.0 | **0.0** |
| 100 | PAYER_LIABILITY | 0.0000 | 1.0000 | **1.0000** | 0.0 | 2500000.0 | **2500000.0** |

---

## 4. Key Findings & Research Conclusions

1. **Global Pro-Rata Order Invariance:** Across all batch sizes ($N=10, 50, 100$) and all 5 ordering regimes, Global PR exhibits $OS_{\text{across}}(HR) = 0.0000$ and $OS_{\text{across}}(\Pi_A) = 0$ paise. Honest recovery remains exactly $50.00\%$ with zero variance.
2. **First Claim and Payer Liability Sensitivity:** Both FC and PL exhibit maximal across-regime sensitivity ($OS_{\text{across}}(HR) = 1.0000$), swinging between $0.00\%$ recovery under `MULE_FIRST` and $100.00\%$ recovery under `HONEST_FIRST`.
3. **Genuine FIFO vs Interleaved FIFO and Arrival Bounds:** Under `GENUINE_FIFO`, because honest and mule claims arrive in a neutral deterministic sequence, honest claims arriving before reserve depletion are settled. Sequential policies (FC and PL) achieve $60.00\%$ ($N=10$), $44.00\%$ ($N=50$), and $52.00\%$ ($N=100$) honest recovery. Under `MULE_FIRST` (front-running bound), honest recovery is driven to $0.00\%$. Under `HONEST_FIRST` (protective bound), honest recovery reaches $100.00\%$. Under `INTERLEAVED_FIFO`, sequential policies alternate payouts, yielding $40.00\%$ ($N=10$) to $50.00\%$ ($N=100$) honest recovery.

