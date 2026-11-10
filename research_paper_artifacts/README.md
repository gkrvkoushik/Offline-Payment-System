# Research-paper result artifacts

Generated from the frozen experiment CSVs in:
`E:/projects/Final-Year/OfflinePayment/version1/results`

This directory is separate from the simulator's source results. The generator
does not rerun simulations, alter settlement logic, or modify the original CSVs.

## Contents

- `figures/`: publication-oriented figures in PNG (400 dpi), PDF and SVG.
- `tables/`: copies of source summary/reconciliation CSVs and LaTeX table files.
- `generation_metadata.json`: input/output inventory.

## Figure inventory

- `fig01_baseline_policy_comparison`
- `fig02_multiseed_policy_comparison`
- `fig03_receiver_scaling_first`
- `fig03_receiver_scaling_last`
- `fig03_receiver_scaling_middle`
- `fig04_reserve_coverage_sensitivity`
- `fig05_permit_denomination_sensitivity`
- `fig06_permit_and_order_conflict_sensitivity`
- `fig07_reserve_ratio_sensitivity`
- `fig08_mule_concentration_multi_mule`
- `fig08_mule_concentration_no_mule`
- `fig08_mule_concentration_single_mule`
- `fig09_claim_size_heterogeneity`
- `fig10_account_splitting`
- `fig11_exp07_ordering_strategy_recovery`
- `fig12_exp07_across_regime_sensitivity`
- `fig13_exp08_funding_compromised_victim`
- `fig13_exp08_funding_honest_payer`
- `fig13_exp08_funding_malicious_payer`
- `fig14_blockchain_audit_performance`

## Interpretation cautions

1. Figures are descriptive visualizations of the archived experiment outputs.
2. Confidence intervals are plotted only where the source summary provides them.
3. EXP-07 deterministic regimes have repeated fixed sequences; zero within-regime
   variation must not be interpreted as evidence of population certainty.
4. EXP-07 genuine FIFO is the project's synthetic mixed-arrival baseline, not an
   empirically observed payment-network arrival distribution.
5. EXP-08 invariance applies only to the fixed claim population, eligibility,
   ordering, policy and reserve configurations tested.
6. Shared-permit conflict results must not be pooled with common-eligibility
   comparisons as though their eligible claim sets were identical.
7. Amounts are converted from paise to INR only for display; archived CSVs remain
   the authoritative numeric source.

Before submitting the paper, verify figure captions, table references, units,
scenario labels and the precise experimental configuration against the paper text.
