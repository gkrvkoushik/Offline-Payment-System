# EXP-08 Funding-Source Invariance & Financial Exposure Report

**Experiment:** EXP-08 Funding-Source Composition Sensitivity  
**Evaluation Date:** 2026-11-09  
**Core Objective:** Empirically verify gross payout invariance under fixed aggregate reserve $S=C+H+F=100,000$ paise and analyze financial liability exposure between payer and issuer.  

---

## 1. Mathematical Formalism & Invariant Definitions

### Invariant 1: Constant Aggregate Reserve ($S$)
$$\forall \text{ composition } i, \quad C_i + H_i + F_i \equiv 100,000 \text{ paise} = ₹1,000$$
Exact integer equality is verified for all 11 compositions with zero tolerance.

### Invariant 2: Gross Payout Invariance
Under fixed claim population (3 claims of ₹500 each), fixed eligibility (all 3 valid), fixed arrival permutation $p$, and fixed settlement policy $\mathcal{P}$:
$$P_{\text{total}}(C, H, F \mid p, \mathcal{P}) \equiv \text{constant} = 100,000 \text{ paise}$$
Gross settlement payout depends solely on the aggregate reserve $S$ and claim eligibility, not on which funding tier supplies the liquidity.

### Invariant 3: Sequential Tier Waterfall Attribution
Liquidity is drawn strictly in priority order: Collateral ($C$) $\to$ Additional Hold ($H$) $\to$ Issuer Guarantee ($F$):
$$F_C = \min(P, C)$$ 
$$F_H = \min(P - F_C, H)$$ 
$$F_F = \min(P - F_C - F_H, F)$$ 
$$F_C + F_H + F_F \equiv P_{\text{total}}$$ 
No tier is ever overdrawn ($F_C \le C, F_H \le H, F_F \le F$), and no balance is negative.

### Invariant 4: Separation of Payer Debit and Institutional Exposure
- **Payer-Owned Debit:** $D_{\text{payer}} = F_C + F_H \le C + H$
- **Issuer Guarantee Expenditure:** $D_{\text{issuer}} = F_F \le F$
- **Conservation of Outflow:** $D_{\text{payer}} + D_{\text{issuer}} \equiv P_{\text{total}}$

---

## 2. Payer Liability & Attacker Profit Modeling

The canonical net economic profit is defined as:
$$\Pi_A = (G_A + R_{\text{mule}}) - (D_{\text{payer}} + C_{\text{attack}})$$ 

1. **Malicious Payer Scenario:**
   - The adversary controls the payer account.
   - Collateral and hold debits ($D_{\text{payer}} = F_C + F_H$) are actual financial losses incurred by the attacker.
   - As funding composition shifts from collateral ($C+H$) to institutional guarantee ($F$), attacker net profit increases linearly with slope:
     $$\frac{\partial \Pi_A}{\partial F} = +1.0$$

2. **Compromised Victim Scenario:**
   - The account owner is an innocent victim whose credentials were stolen.
   - Payer debits are suffered by the victim, not the attacker ($D_{\text{payer}} = 0$).
   - Attacker net profit is strictly decoupled from the funding tier mix ($\Pi_A = G_A + R_{\text{mule}}$) and remains constant across all 11 compositions.

3. **Honest Payer Scenario:**
   - Standard dispute baseline where the payer covers approved offline transactions ($D_{\text{payer}} = F_C + F_H$).
   - Third-party mule payouts are tracked as gross cashout proceeds without POS goods released.

---

## 3. Reconciliation & Verification Results

All 594 evaluation runs were audited against all financial invariants:

| Invariant Audit Item | Theoretical Condition | Runs Evaluated | Invariant Violations | Reconciliation Status |
| :--- | :--- | :---: | :---: | :---: |
| Total Reserve Constant | $C + H + F \equiv 100,000$ paise | 594 | 0 | **PASSED (100%)** |
| Tiers Not Overdrawn | $F_C \le C, F_H \le H, F_F \le F$ | 594 | 0 | **PASSED (100%)** |
| Sources Sum to Payout | $F_C + F_H + F_F \equiv P_{\text{total}}$ | 594 | 0 | **PASSED (100%)** |
| Payout Bounded by Reserve | $P_{\text{total}} \le S$ | 594 | 0 | **PASSED (100%)** |
| Gross Payout Invariance | $P_{\text{total}} = 100,000$ across compositions | 594 | 0 | **PASSED (100%)** |
| Overall Reconciliation | All invariants hold simultaneously | 594 | 0 | **PASSED (100%)** |

---

## 4. Scope, Generalizability & Methodological Limitations

> [!NOTE]
> **Scope and Controlled Setup:** EXP-08 evaluates a controlled configuration with total reserve $S = 100,000$ paise ($₹1,000$) and three claims of ₹500 each (aggregate claim value $X = 150,000$ paise).

> [!WARNING]
> **Generalizability Caution:** While gross payout invariance is proven for fixed claim populations and fixed total reserve under the formal waterfall, this controlled test does not imply that funding composition has zero effect under unconstrained real-world settings where collateral thresholds might dynamically alter permit issuance, credit limits, or offline acceptance trust levels.

