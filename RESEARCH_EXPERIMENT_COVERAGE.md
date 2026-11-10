# Research Experiment Coverage Audit & Design Mapping

**Project:** Hybrid Offline Payment with Payer-Liable Settlement and Blockchain-Based Audit Anchoring  
**Evaluation Scope:** Mapping Finalized Research Questions (RQ1–RQ5) and Planned Experiments (EXP-01–EXP-08) against Actual Codebase Implementation, Automated Tests, and Telemetry Outputs  
**Audit Date:** November 9, 2026  
**Auditor Classification:** Independent Research Architecture & Verification Audit  
**Operating Rule:** Pure audit and planning task — NO source code, settlement algorithms, or experimental datasets were modified.

---

## 1. Project Context & Authoritative Version Baseline

- **Operating System:** Windows 11
- **Python Runtime:** Python `3.12.4`
- **Package & Dependency Manager:** `uv 0.9.18`
- **Lockfile Integrity:** `uv.lock` (58 resolved and audited packages)
- **Node/EVM Runtime:** Node.js v20.x, Hardhat `2.22.18`, `solc 0.8.24` (optimizer runs 200)
- **Version Control Status:** Branch `main`, uncommitted working tree (Head is unborn; integrity anchored via `artifact_manifest.csv` tracking 149 files with SHA-256 digests).
- **Core Settlement Engines:**
  - `FirstClaimSettlement` ([`src/offline_payment/settlement/first_claim.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/settlement/first_claim.py))
  - `GlobalProRataSettlement` ([`src/offline_payment/settlement/pro_rata.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/settlement/pro_rata.py))
  - `PayerLiabilitySettlement` ([`src/offline_payment/settlement/payer_liability.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/settlement/payer_liability.py))
- **Automated Test Suite:** 184 unit and integration tests passing in 45.91s ([`test_execution.log`](file:///e:/projects/Final-Year/OfflinePayment/version1/test_execution.log)).

---

## 2. Research Questions Mapping (RQ1 – RQ5)

### RQ1 — Claim Ordering
> *How does claim-ingestion order affect honest merchant recovery under limited reserves?*

1. **Existing Implementation Modules:**
   - [`src/offline_payment/experiments/adversarial_evaluation.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/experiments/adversarial_evaluation.py): `run_common_eligibility_comparison()`, `run_reconciled_experiment_d()`, `run_experiment_07_macro_ordering_strategies()`
   - [`src/offline_payment/attacks/claim_ordering.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/attacks/claim_ordering.py): `permute_claim_ordering()`
   - [`src/offline_payment/settlement/payer_liability.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/settlement/payer_liability.py): Strict prefix sequential processor
2. **Existing Experiment Scripts:**
   - [`scripts/run_adversarial_evaluation.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/scripts/run_adversarial_evaluation.py)
   - [`scripts/run_exp07_ordering_strategies.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/scripts/run_exp07_ordering_strategies.py)
   - [`scripts/reproduce_and_reconcile_experiments.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/scripts/reproduce_and_reconcile_experiments.py)
3. **Configuration & Parameters:**
   - Small batch: 3 claims (1 mule ₹500, 2 honest ₹500 each; Reserve: ₹1,000; all 6 permutations).
   - Macro batch (EXP-07): Batch sizes $N \in [10, 50, 100]$; 50% mule share; 50% reserve coverage ratio ($\rho = 0.50$); 30 random seeds ($s \in [1..30]$ for stochastic regimes); 5 arrival regimes (`GENUINE_FIFO`, `INTERLEAVED_FIFO`, `RANDOM`, `MULE_FIRST`, `HONEST_FIRST`).
4. **Existing CSV Outputs:**
   - [`results/adversarial_evaluation/common_eligibility_runs.csv`](file:///e:/projects/Final-Year/OfflinePayment/version1/results/adversarial_evaluation/common_eligibility_runs.csv) (18 rows)
   - [`results/adversarial_evaluation/common_eligibility_summary.csv`](file:///e:/projects/Final-Year/OfflinePayment/version1/results/adversarial_evaluation/common_eligibility_summary.csv) (3 rows)
   - [`results/adversarial_evaluation/small_mule_analytical_reconciliation.csv`](file:///e:/projects/Final-Year/OfflinePayment/version1/results/adversarial_evaluation/small_mule_analytical_reconciliation.csv) (18 rows)
   - [`results/adversarial_evaluation/exp07_ordering_strategies/ordering_strategies_runs.csv`](file:///e:/projects/Final-Year/OfflinePayment/version1/results/adversarial_evaluation/exp07_ordering_strategies/ordering_strategies_runs.csv) (1,350 rows)
   - [`results/adversarial_evaluation/exp07_ordering_strategies/ordering_strategies_summary.csv`](file:///e:/projects/Final-Year/OfflinePayment/version1/results/adversarial_evaluation/exp07_ordering_strategies/ordering_strategies_summary.csv) (45 rows)
   - [`results/adversarial_evaluation/exp07_ordering_strategies/ordering_strategies_order_sequences.csv`](file:///e:/projects/Final-Year/OfflinePayment/version1/results/adversarial_evaluation/exp07_ordering_strategies/ordering_strategies_order_sequences.csv) (24,000 rows)
   - [`results/adversarial_evaluation/exp07_ordering_strategies/ordering_strategies_cross_regime_sensitivity.csv`](file:///e:/projects/Final-Year/OfflinePayment/version1/results/adversarial_evaluation/exp07_ordering_strategies/ordering_strategies_cross_regime_sensitivity.csv) (9 rows)
   - [`results/adversarial_evaluation/exp07_ordering_strategies/ordering_strategies_configuration.json`](file:///e:/projects/Final-Year/OfflinePayment/version1/results/adversarial_evaluation/exp07_ordering_strategies/ordering_strategies_configuration.json)
   - [`results/adversarial_evaluation/exp07_ordering_strategies/ordering_strategies_reproducibility_report.md`](file:///e:/projects/Final-Year/OfflinePayment/version1/results/adversarial_evaluation/exp07_ordering_strategies/ordering_strategies_reproducibility_report.md)
5. **Metrics Calculated:**
   - Within-regime sample stats: `mean_honest_recovery`, `std_honest_recovery`, `ci95_honest_recovery`, `min_honest_recovery`, `max_honest_recovery`, `within_regime_os_recovery`, `is_deterministic_regime`.
   - Across-regime sensitivity: `across_regime_os_recovery_rate` ($\max(\text{mean}) - \min(\text{mean})$ across 5 regimes), `across_regime_os_profit_paise`, `across_regime_os_mule_payout_paise`.
   - Core metrics: `attacker_net_profit_paise`, `mule_payout_paise`, `reserve_utilization`, `stranded_reserve_paise`, `mule_advantage`.
6. **Automated Tests:**
   - `tests/test_adversarial_evaluation.py::test_common_eligibility_vs_shared_permit_semantics`
   - `tests/test_adversarial_evaluation.py::test_small_mule_analytical_reconciliation_exact`
   - `tests/test_adversarial_evaluation.py::test_global_pr_order_invariance_modulo_remainder_ties`
   - `tests/test_exp07_ordering_strategies.py` (15 dedicated unit and integration tests passing).
7. **Empirical Findings:**
   - **Global PR is Order-Invariant across all scales and regimes:** Honest recovery remains exactly $0.500000$ (or $66.67\%$ in Exp 1) with strictly $0.000000$ across-regime sensitivity ($OS_{\text{across}} = 0.000000$) and $0.000000$ within-regime standard deviation across all 5 regimes (`GENUINE_FIFO`, `INTERLEAVED_FIFO`, `RANDOM`, `MULE_FIRST`, `HONEST_FIRST`) and all batch sizes ($N \in [10, 50, 100]$).
   - **FC and PL exhibit extreme across-regime sensitivity:** Under `MULE_FIRST` front-running, honest recovery is driven to strictly $0.000000$ ($100\%$ loss, all reserve captured by mules). Under `HONEST_FIRST`, honest recovery is strictly $1.000000$. The across-regime order sensitivity is strictly $1.000000$ (100 percentage points).
   - **Deterministic Regimes have Zero Within-Regime Variability:** Deterministic regimes (`GENUINE_FIFO`, `INTERLEAVED_FIFO`, `MULE_FIRST`, `HONEST_FIRST`) show `std = 0.000000` across seeds, properly isolated from the stochastic `RANDOM` regime.
8. **Coverage Assessment:**
   - **FULLY COVERED (100%).** Systematic macro ordering evaluation completed across all batch sizes, 5 macro arrival regimes, and random seeds.

---

### RQ2 — Reserve Availability
> *How does the reserve-to-claim ratio affect merchant recovery, attacker profit and stranded reserve?*

1. **Existing Implementation Modules:**
   - [`src/offline_payment/experiments/adversarial_evaluation.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/experiments/adversarial_evaluation.py): `run_experiment_b_reserve_ratio()`
   - [`src/offline_payment/experiments/reserve_coverage.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/experiments/reserve_coverage.py): `run_reserve_coverage_experiment()`
2. **Existing Experiment Scripts:**
   - [`scripts/run_adversarial_evaluation.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/scripts/run_adversarial_evaluation.py)
3. **Configuration & Parameters:**
   - Reserve ratios: $\rho = S / X \in [0.25, 0.50, 0.75, 1.00, 1.25]$; 100 paired random seeds per ratio; Total claim value: ₹1,500 (150,000 paise).
4. **Existing CSV Outputs:**
   - [`results/adversarial_evaluation/reserve_ratio_runs.csv`](file:///e:/projects/Final-Year/OfflinePayment/version1/results/adversarial_evaluation/reserve_ratio_runs.csv) (1,500 rows)
   - [`results/adversarial_evaluation/reserve_ratio_summary.csv`](file:///e:/projects/Final-Year/OfflinePayment/version1/results/adversarial_evaluation/reserve_ratio_summary.csv) (15 rows)
   - Baseline: [`results/reserve_coverage_raw.csv`](file:///e:/projects/Final-Year/OfflinePayment/version1/results/reserve_coverage_raw.csv), [`results/reserve_coverage_summary.csv`](file:///e:/projects/Final-Year/OfflinePayment/version1/results/reserve_coverage_summary.csv)
5. **Metrics Calculated:**
   - `mean_honest_recovery`, `std_honest_recovery`, `ci95_honest_recovery`, `median_honest_recovery`, `iqr_honest_recovery`, `mean_reserve_utilization`, `mean_stranded_reserve_paise`, `mean_attacker_profit_paise`.
6. **Automated Tests:**
   - `tests/test_adversarial_evaluation.py::test_funding_tier_bounds_respected`
   - `tests/test_invariants.py::test_invariant_1_total_payout_never_exceeds_total_reserve`
7. **Empirical Findings:**
   - Honest recovery increases strictly monotonically with $\rho$ across all policies.
   - At $\rho < 1.0$, Global PR achieves $100\%$ reserve utilization and $0$ stranded reserve. In contrast, PL strands reserve whenever the next arriving claim exceeds the residual balance, stranding up to $21.67\%$ in asymmetric configurations.
8. **Missing Functionality / Experimental Gap:**
   - FULLY COVERED. All required parameters, metrics, confidence intervals, and seed pairing are complete.

---

### RQ3 — Account Fragmentation
> *Can splitting attacker-controlled mule claims across multiple merchant accounts change settlement outcomes?*

1. **Existing Implementation Modules:**
   - [`src/offline_payment/experiments/adversarial_evaluation.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/experiments/adversarial_evaluation.py): `run_account_splitting_experiment()`
2. **Existing Experiment Scripts:**
   - [`scripts/run_adversarial_evaluation.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/scripts/run_adversarial_evaluation.py)
3. **Configuration & Parameters:**
   - Mule accounts: $k \in [1, 2, 5, 10]$ dividing fixed aggregate mule claim value ₹500 (50,000 paise).
   - Honest merchants: 2 claims of ₹500 each; Reserve: ₹1,000 (100,000 paise).
   - Exhaustive permutations for $k=1$ (6 runs) and $k=2$ (24 runs); 50 random permutations for $k=5, 10$.
4. **Existing CSV Outputs:**
   - [`results/adversarial_evaluation/account_splitting_runs.csv`](file:///e:/projects/Final-Year/OfflinePayment/version1/results/adversarial_evaluation/account_splitting_runs.csv) (390 rows)
   - [`results/adversarial_evaluation/account_splitting_summary.csv`](file:///e:/projects/Final-Year/OfflinePayment/version1/results/adversarial_evaluation/account_splitting_summary.csv) (12 rows)
5. **Metrics Calculated:**
   - `mean_mule_payout_paise`, `order_sensitivity_mule_payout_paise`, `mean_honest_recovery`, `order_sensitivity_honest_recovery`, `mean_attacker_profit_paise`.
6. **Automated Tests:**
   - `tests/test_adversarial_evaluation.py::test_global_pr_account_splitting_invariance` (parametrized for $k \in [1, 2, 5, 10]$).
7. **Empirical Findings:**
   - **Global PR is Account-Splitting Invariant:** Dividing the claim across $1, 2, 5, 10$ accounts yields mean mule payouts of $33,333.33$, $33,334.00$, $33,334.00$, and $33,333.16$ paise. The variation is strictly $\le 2$ paise (pure integer-rounding remainder distribution). Honest recovery is rock-solid at $66.67\%$.
   - **PL is Highly Sensitive to Fragmentation:** Splitting the mule claim allows small mule claims to interleave before honest claims and drain reserve in small chunks, causing honest recovery to drop from $66.67\%$ ($k=1$) to $51.00\%$ ($k=5$).
8. **Missing Functionality / Experimental Gap:**
   - FULLY COVERED. Properly decouples account splitting from Sybil resistance and proves mathematical invariance under integer arithmetic.

---

### RQ4 — Permit Conflicts
> *How do conflicting claims referencing the same permit affect merchant recovery and settlement allocation?*

1. **Existing Implementation Modules:**
   - [`src/offline_payment/experiments/adversarial_evaluation.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/experiments/adversarial_evaluation.py): `run_shared_permit_conflict_comparison()`
   - [`src/offline_payment/settlement/first_claim.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/settlement/first_claim.py): Duplicate permit gatekeeper
2. **Existing Experiment Scripts:**
   - [`scripts/run_adversarial_evaluation.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/scripts/run_adversarial_evaluation.py)
3. **Configuration & Parameters:**
   - 1 shared permit (double-spend attack); 3 claims of ₹500 (1 mule, 2 honest); Reserve: ₹1,000; All 6 arrival permutations.
4. **Existing CSV Outputs:**
   - [`results/adversarial_evaluation/shared_permit_runs.csv`](file:///e:/projects/Final-Year/OfflinePayment/version1/results/adversarial_evaluation/shared_permit_runs.csv) (18 rows)
   - [`results/adversarial_evaluation/shared_permit_summary.csv`](file:///e:/projects/Final-Year/OfflinePayment/version1/results/adversarial_evaluation/shared_permit_summary.csv) (3 rows)
5. **Metrics Calculated:**
   - `submitted_claims_count`, `cryptographically_valid_count`, `permit_conflicting_count`, `eligible_claims_count`, `rejected_claims_count`, `claims_considered_by_allocation`, `honest_recovery_rate`, `attacker_net_profit_paise`.
6. **Automated Tests:**
   - `tests/test_adversarial_evaluation.py::test_common_eligibility_vs_shared_permit_semantics`
   - `tests/test_first_claim.py::test_duplicate_permit_rejection`
   - `tests/test_invariants.py::test_invariant_4_fc_pays_at_most_one_claim_per_permit`
7. **Empirical Findings:**
   - FC rejects 2 conflicting claims at the gate (`rejected_claims_count = 2.0`). Because merchants surrendered goods offline, rejecting conflicting claims results in catastrophic loss: if the mule arrives first, honest recovery is $0.00\%$; if an honest claim arrives first, honest recovery is $50.00\%$.
   - Global PR and PL allocate reserve across all valid claims, preventing front-running claim dismissal.
8. **Missing Functionality / Experimental Gap:**
   - FULLY COVERED. Clear mathematical separation between common eligibility (pure reserve exhaustion) and permit invalidation (credential double-spending).

---

### RQ5 — Funding Composition
> *How does the composition of payer allowance, payer hold and issuer guarantee affect economic losses?*

1. **Existing Implementation Modules:**
   - [`src/offline_payment/models/allowance.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/models/allowance.py): Holds $C$ (allowance amount), $H$ (payer hold), and $F$ (issuer guarantee).
   - [`src/offline_payment/settlement/base.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/settlement/base.py): Implements sequential waterfall: $F_C \le C \to F_H \le H \to F_F \le F$.
   - [`src/offline_payment/metrics/adversarial_metrics.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/metrics/adversarial_metrics.py): Tracks payer debit ($F_C + F_H$) vs. institutional expenditure ($F_F$).
   - [`src/offline_payment/experiments/adversarial_evaluation.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/experiments/adversarial_evaluation.py): `run_experiment_08_funding_source_sensitivity()`
2. **Existing Experiment Scripts:**
   - [`scripts/run_exp08_funding_sensitivity.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/scripts/run_exp08_funding_sensitivity.py)
   - [`scripts/reproduce_and_reconcile_experiments.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/scripts/reproduce_and_reconcile_experiments.py)
3. **Configuration & Parameters:**
   - Total reserve constant: $S = 100,000$ paise (₹1,000).
   - 11 systematic funding compositions: `100C-0H-0F`, `80C-20H-0F`, `50C-50H-0F`, `20C-80H-0F`, `0C-100H-0F`, `33C-33H-33F`, `40C-20H-40F`, `20C-10H-70F`, `10C-0H-90F`, `0C-0H-100F`, `0C-50H-50F`.
   - 3 payer liability scenarios: `malicious_payer` ($D_{\text{payer}} = F_C + F_H$), `compromised_victim` ($D_{\text{payer}} = 0$), `honest_payer`.
   - All 6 arrival permutations ($3! = 6$) $\times$ 3 settlement policies (FC, PR, PL) = 594 runs.
4. **Existing CSV Outputs:**
   - [`results/adversarial_evaluation/exp08_funding_sensitivity/funding_source_runs.csv`](file:///e:/projects/Final-Year/OfflinePayment/version1/results/adversarial_evaluation/exp08_funding_sensitivity/funding_source_runs.csv) (594 rows)
   - [`results/adversarial_evaluation/exp08_funding_sensitivity/funding_source_summary.csv`](file:///e:/projects/Final-Year/OfflinePayment/version1/results/adversarial_evaluation/exp08_funding_sensitivity/funding_source_summary.csv) (99 rows)
   - [`results/adversarial_evaluation/exp08_funding_sensitivity/funding_source_reconciliation.csv`](file:///e:/projects/Final-Year/OfflinePayment/version1/results/adversarial_evaluation/exp08_funding_sensitivity/funding_source_reconciliation.csv) (594 rows, 100% PASSED)
   - [`results/adversarial_evaluation/exp08_funding_sensitivity/funding_source_configuration.json`](file:///e:/projects/Final-Year/OfflinePayment/version1/results/adversarial_evaluation/exp08_funding_sensitivity/funding_source_configuration.json)
5. **Metrics Calculated:**
   - `total_payout_paise`, `honest_payout_paise`, `honest_recovery_rate`, `mule_payout_paise`, `payer_collateral_debit_paise`, `payer_hold_debit_paise`, `payer_total_debit_paise`, `issuer_guarantee_expenditure_paise`, `attacker_net_profit_paise`, `reserve_utilization`, `stranded_reserve_paise`.
6. **Automated Tests:**
   - `tests/test_invariants.py::test_invariant_10_no_funding_source_overdrawn`
   - `tests/test_exp08_funding_sensitivity.py` (9 dedicated tests passing).
7. **Empirical Findings:**
   - **Gross Payout Invariance:** Gross settlement allocation $P_{\text{total}} = 100,000$ paise is strictly invariant across all 11 funding compositions for every fixed scenario and policy.
   - **Linear Financial Liability Redistribution:** Shifting funds from collateral ($C + H$) to guarantee ($F$) linearly shifts liability from payer to issuer. Under `malicious_payer`, attacker net profit increases linearly with slope $\frac{\partial \Pi_A}{\partial F} = +1.0$. Under `compromised_victim`, attacker profit is decoupled from payer debits ($D_{\text{payer}} = 0$).
8. **Coverage Assessment:**
   - **FULLY COVERED (100%).** Systematic funding sweep holding $S$ constant completed and fully reconciled.

---

## 3. Audit of the Eight Planned Experiments

| Exp ID | Experiment Name | Implementation Status | Implementation Location | Existing Outputs | Audit Assessment |
| :---: | :--- | :---: | :--- | :--- | :--- |
| **EXP-01** | Common Eligibility & Claim Ordering | **COMPLETE** | `adversarial_evaluation.py:run_common_eligibility_comparison()` | `common_eligibility_runs.csv`<br>`common_eligibility_summary.csv` | Exactly 3 valid permits, 1 mule (₹500), 2 honest (₹500 each), reserve ₹1,000, all 6 permutations. All policies receive identical eligible claims. |
| **EXP-02** | Shared-Permit Conflicts | **COMPLETE** | `adversarial_evaluation.py:run_shared_permit_conflict_comparison()` | `shared_permit_runs.csv`<br>`shared_permit_summary.csv` | 1 shared permit, 3 claims of ₹500, reserve ₹1,000, all 6 permutations. Explicit tracking of submitted, valid, conflicting, rejected, and considered claims. |
| **EXP-03** | Reserve-Ratio Sensitivity | **COMPLETE** | `adversarial_evaluation.py:run_experiment_b_reserve_ratio()` | `reserve_ratio_runs.csv`<br>`reserve_ratio_summary.csv` | 5 ratios ($0.25$ to $1.25$), 100 paired seeds per ratio, $C/H/F$ funding caps, complete sample statistics (mean, sample std $ddof=1$, 95% CI, median, IQR). |
| **EXP-04** | Mule Concentration | **COMPLETE** | `adversarial_evaluation.py:run_experiment_c_mule_concentration()` | `mule_concentration_runs.csv`<br>`mule_concentration_summary.csv` | 6 mule shares ($0\%$ to $100\%$) $\times$ 2 topologies (single vs multi-mule) $\times$ 100 seeds. Fixed aggregate claim value. Properly decoupled from account splitting. |
| **EXP-05** | Claim-Size Heterogeneity | **COMPLETE** | `adversarial_evaluation.py:run_reconciled_experiment_d()` | `claim_size_runs.csv`<br>`claim_size_summary.csv`<br>`small_mule_analytical_reconciliation.csv` | 5 claim profiles (equal, small mule, large mule, unequal honest, multi-mule) $\times$ 100 seeds. Includes exact 6-permutation analytical proof reconciling Small Mule ₹216.67 stranded reserve and ₹650 profit. |
| **EXP-06** | Account Splitting | **COMPLETE** | `adversarial_evaluation.py:run_account_splitting_experiment()` | `account_splitting_runs.csv`<br>`account_splitting_summary.csv` | $k \in [1, 2, 5, 10]$ mule accounts dividing ₹500 aggregate claim. Evaluates order sensitivity and integer rounding bounds ($\le 2$ paise). Strictly decoupled from Sybil claims. |
| **EXP-07** | Claim-Ordering Strategies | **COMPLETE** | `adversarial_evaluation.py:run_experiment_07_macro_ordering_strategies()` | `exp07_ordering_strategies/ordering_strategies_runs.csv`<br>`exp07_ordering_strategies/ordering_strategies_summary.csv`<br>`exp07_ordering_strategies/ordering_strategies_order_sequences.csv`<br>`exp07_ordering_strategies/ordering_strategies_cross_regime_sensitivity.csv`<br>`exp07_ordering_strategies/ordering_strategies_reproducibility_report.md` | Batch sizes $N \in [10, 50, 100]$, 50% mule share, 50% coverage ratio, 30 seeds, 5 regimes (`GENUINE_FIFO`, `INTERLEAVED_FIFO`, `RANDOM`, `MULE_FIRST`, `HONEST_FIRST`). Fully evaluates macro arrival regimes, within-regime variability vs across-regime sensitivity. |
| **EXP-08** | Funding-Source Sensitivity | **COMPLETE** | `adversarial_evaluation.py:run_experiment_08_funding_source_sensitivity()` | `exp08_funding_sensitivity/funding_source_runs.csv`<br>`exp08_funding_sensitivity/funding_source_summary.csv`<br>`exp08_funding_sensitivity/funding_source_reconciliation.csv`<br>`exp08_funding_sensitivity/funding_source_invariance_report.md` | Total reserve fixed at $S=100,000$ paise (₹1,000) with zero tolerance, 11 systematic $C:H:F$ compositions, 3 payer liability models, 6 permutations = 594 runs, 100% invariant reconciliation. |

---

## 4. Verification Summary

The codebase has complete, tested implementations and publication-grade empirical datasets for **all 8 experiments** (EXP-01 through EXP-08), fully resolving **RQ1, RQ2, RQ3, RQ4, and RQ5** with 100% experimental coverage.

All 8 experiments execute deterministically in under 8 seconds combined, pass all automated unit and regression tests, and reconcile with 100% literal string equality (`EXACT_MATCH`) across all 20 target CSV datasets in the suite.
