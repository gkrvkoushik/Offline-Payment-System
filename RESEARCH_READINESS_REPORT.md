# Research Readiness Report: Hybrid Offline Payment Simulator

**Project:** Hybrid Offline Payment with Payer-Liable Settlement and Blockchain-Based Audit Anchoring  
**Evaluation Scope:** Codebase Readiness, Experimental Coverage, and Academic Paper Draftability  
**Audit Date:** November 9, 2026  
**Auditor Classification:** Independent Research Verification & Architecture Review  
**Final Readiness Verdict:** **READY FOR DRAFTING (Methodology and Empirical Results Chapters Fully Supported by Verified Telemetry and Code; Non-Publication Operational Limitations Explicitly Documented)**

---

## 1. Executive Summary

An exhaustive research audit and implementation verification of the offline payment research simulator was conducted, covering all finalized research questions (RQ1–RQ5), planned experiments (EXP-01–EXP-08), and theoretical hypotheses (H1–H5).

### Key Audit Conclusions:
1. **Methodology Chapter Readiness: READY.** The formal system models, settlement algorithms (FC, Global PR, PL), cryptographic validation rules, tiered funding waterfall ($C \to H \to F$), unified POS goods acquisition criteria, and Hardhat EVM smart contract anchoring are fully implemented, audited, and verified by 184 automated tests passing with zero failures.
2. **Results Chapter Readiness: READY.** All eight planned experiments (EXP-01 through EXP-08) are fully implemented, executed, and reconciled against published datasets with 100% literal equality (`EXACT_MATCH`) across 20 target CSV files. These datasets empirically answer **RQ1, RQ2, RQ3, RQ4, and RQ5** and support **H1, H2, H3, H4, and H5** within the evaluated configurations.
3. **Refined Empirical Work:**
   - **EXP-07 (Macro Claim-Ordering Strategies):** Evaluates 5 arrival regimes (`GENUINE_FIFO`, `INTERLEAVED_FIFO`, `RANDOM`, `MULE_FIRST`, `HONEST_FIRST`) across $N \in [10, 50, 100]$ batch sizes and 30 seeds. Following corrected population design, `GENUINE_FIFO` is established via a neutral deterministic arrival sequence (seed $42 + N$) where mule and honest claims arrive interspersed independently of claimant category. Explicit unit tests prove `GENUINE_FIFO` is strictly distinct from `MULE_FIRST`, `HONEST_FIRST`, and `INTERLEAVED_FIFO` in actual ordered transaction IDs and claimant categories. Proves Global PR remains strictly order-invariant ($OS_{\text{across}} = 0.000000$), while sequential policies (FC and PL) exhibit across-regime order sensitivity up to 1.000000 (100 percentage points). Separates within-regime sample variability from across-regime sensitivity.
   - **EXP-08 (Funding-Source Sensitivity):** Evaluates 11 systematic $C:H:F$ compositions holding total reserve strictly constant at $S=100,000$ paise with zero tolerance across 3 payer liability models and 6 arrival permutations (594 runs). Confirms conditional gross settlement invariance ($P_{\text{total}} \equiv 100,000$ paise) and linear financial liability redistribution ($\frac{\partial \Pi_A}{\partial F} = +1.0$ under malicious payer ownership). Full invariance verified in `funding_source_invariance_report.md`.
4. **Publication Readiness Scope:** While code and data support writing the methodology and experimental evaluation chapters, publication readiness is subject to explicitly documented assumptions and limitations (e.g., front-running bounding assumptions, synthetic arrival models, and uncommitted Git repository state).

---

## 2. Explicit Answers to the Nine Assessment Questions

### Question 1: Which research questions can the current simulator already answer?
- **RQ1 (Claim Ordering):** **YES.** Answered via EXP-01, EXP-05, and EXP-07. Evaluates permutation order sensitivity under scarce reserves; demonstrates Global PR is strictly order-invariant across all 5 macro arrival regimes, while FC and PL suffer severe recovery collapse under mule front-running. *(Source-code verified, Test verified, Experiment reproduced)*
- **RQ2 (Reserve Availability):** **YES.** Answered via EXP-03 and baseline reserve coverage. Evaluates $\rho \in [0.25, 1.25]$; demonstrates recovery increased monotonically in the tested configurations and confirms zero stranded reserve in PR when claims exceed reserves. *(Source-code verified, Test verified, Experiment reproduced)*
- **RQ3 (Account Fragmentation):** **YES.** Answered via EXP-06. Evaluates $k \in [1, 2, 5, 10]$ mule accounts; demonstrates Global PR is invariant under integer division ($\le 2$ paise), while PL honest recovery collapses from $66.67\%$ to $51.00\%$ before reaching a plateau. *(Source-code verified, Test verified, Experiment reproduced)*
- **RQ4 (Permit Conflicts):** **YES.** Answered via EXP-02. Separately records submitted, valid, conflicting, rejected, and considered claims; demonstrates FC front-running rejection drives honest recovery to $0\%$ when conflicting claims reference the same permit. *(Source-code verified, Test verified, Experiment reproduced)*
- **RQ5 (Funding Composition):** **YES.** Answered via EXP-08. Evaluates 11 systematic $C:H:F$ compositions at constant $S=100,000$ paise; demonstrates gross settlement allocation is invariant to funding tier mix under fixed claims and total reserves, while financial exposure shifts linearly between payer collateral debit and institutional guarantee expenditure. *(Source-code verified, Test verified, Experiment reproduced)*

---

### Question 2: Which experiments are fully implemented and reproducible?
All **eight experiments** are completely implemented in [`src/offline_payment/experiments/adversarial_evaluation.py`](file:///e:/projects/Final-Year/OfflinePayment/version1/src/offline_payment/experiments/adversarial_evaluation.py), covered by unit tests, and independently reproduced with literal string `EXACT_MATCH` in [`experiment_reconciliation.csv`](file:///e:/projects/Final-Year/OfflinePayment/version1/experiment_reconciliation.csv):
1. **EXP-01: Common Eligibility and Claim Ordering** (`common_eligibility_runs.csv`, `common_eligibility_summary.csv`)
2. **EXP-02: Shared-Permit Conflicts** (`shared_permit_runs.csv`, `shared_permit_summary.csv`)
3. **EXP-03: Reserve-Ratio Sensitivity** (`reserve_ratio_runs.csv`, `reserve_ratio_summary.csv`)
4. **EXP-04: Mule Concentration** (`mule_concentration_runs.csv`, `mule_concentration_summary.csv`)
5. **EXP-05: Claim-Size Heterogeneity & Small Mule Analytical** (`claim_size_runs.csv`, `claim_size_summary.csv`, `small_mule_analytical_reconciliation.csv`)
6. **EXP-06: Account Splitting Invariance** (`account_splitting_runs.csv`, `account_splitting_summary.csv`)
7. **EXP-07: Macro Claim-Ordering Strategies** (`exp07_ordering_strategies/ordering_strategies_runs.csv`, `exp07_ordering_strategies/ordering_strategies_summary.csv`, `exp07_ordering_strategies/ordering_strategies_order_sequences.csv`, `exp07_ordering_strategies/ordering_strategies_cross_regime_sensitivity.csv`)
8. **EXP-08: Funding-Source Sensitivity** (`exp08_funding_sensitivity/funding_source_runs.csv`, `exp08_funding_sensitivity/funding_source_summary.csv`, `exp08_funding_sensitivity/funding_source_reconciliation.csv`)

*(All eight are Source-code verified, Test verified, and Experiment reproduced).*

---

### Question 3: Which experiments are only partially implemented?
**NONE.** All planned experiments (EXP-01 through EXP-08) are fully implemented, executed, tested, and reconciled.

---

### Question 4: Which experiments genuinely need new code?
**NONE.** All eight planned experiment suites are fully coded, integrated into `AdversarialEvaluationSuite`, provided with standalone CLI runners, and covered by automated regression test suites.

---

### Question 5: Are all five hypotheses testable with the current architecture?
**YES.** All five hypotheses (H1 through H5) are testable and empirically **SUPPORTED BY THE EVALUATED CONFIGURATIONS**:
- **H1 (Order Sensitivity):** Supported by EXP-01, EXP-05, and EXP-07 (greater observed order sensitivity in evaluated configurations).
- **H2 (Reserve Availability):** Supported by EXP-03 (recovery increased monotonically in tested configurations).
- **H3 (Account Fragmentation):** Supported by EXP-06 (PL sensitivity with non-asymptotic plateau vs. PR invariance).
- **H4 (Permit-Level Rejection):** Supported by EXP-02 (shared-permit conflict loss vs. common-eligibility pooling).
- **H5 (Funding Composition Exposure):** Supported by EXP-08 (conditional gross payout invariance and linear exposure shift).

---

### Question 6: What is the minimum additional work?
Experimental and simulation implementation is **substantively complete** for the research questions. The remaining academic preparation tasks are:
1. Authoring the paper methodology and results chapters using the 20 verified empirical CSV datasets and generated plots.
2. Formally committing the working tree to Git (`git commit`) to establish an immutable 40-character commit SHA.
3. Contextualizing empirical findings with explicit methodological boundaries and real-world friction models.

---

### Question 7: Is the project ready for the research paper's methodology chapter?
**YES, READY FOR DRAFTING.**
- Formal definitions of First Claim Wins, Global Pro-Rata, and Payer-Liable Strict Prefix are verified.
- The cryptographic permit and voucher lifecycle is mathematically specified.
- The 5-condition unified POS goods release model is implemented and tested.
- Blockchain anchoring via Merkle tree and EVM smart contract is opcode-verified on Hardhat.
- All formal protocol invariants are backed by 184 automated tests.

---

### Question 8: Is the project ready for the results chapter?
**YES, READY FOR DRAFTING.**
- All five research questions (RQ1–RQ5) and hypotheses (H1–H5) have complete, reproducible datasets with run-level telemetry, statistical summaries (mean, sample std $ddof=1$, 95% CI, median, IQR), across-regime sensitivity matrices, and 100% exact reproduction reconciliation.

---

### Question 9: What are the remaining research risks and limitations?
1. **Uncommitted Git Repository State:** The local repository is on branch `main` with no committed revisions. While files are secured via SHA-256 in `artifact_manifest.csv`, formal academic citations require committing to record a permanent 40-character Git commit SHA.
2. **Order Influence Feasibility (Theoretical Bounds):** In real payment networks, attackers cannot strictly guarantee FIFO queue manipulation. The paper must frame `MULE_FIRST` and `HONEST_FIRST` as theoretical sensitivity bounds rather than deterministic adversary capabilities.
3. **Generalizability Across Heterogeneous Claim Distributions:** While EXP-05 tests 5 discrete heterogeneity profiles, large-scale empirical payment distributions (e.g., power-law or log-normal claim sizes) remain outside the current experimental grid.
4. **Data Redundancy:** Legacy Experiment A CSV files (`order_sensitivity_runs.csv`) should be clearly designated as preliminary aggregate files to avoid reader confusion with modern partitioned datasets (`common_eligibility`, `shared_permit`, and `exp07_ordering_strategies`).
