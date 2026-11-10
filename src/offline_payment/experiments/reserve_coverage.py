"""Experiment: Reserve coverage sweep (S/X ratio sensitivity).

Varies total reserve coverage ratio S/X across:
  [0.10, 0.25, 0.50, 0.667, 0.75, 1.00, 1.25, 1.50]
Compares FC, PR, and PL under identical claims and ingestion orders.
"""

from typing import Dict, List, Optional
import csv
import os

from offline_payment.config import ClaimType, PAISE_PER_INR
from offline_payment.models.allowance import Allowance
from offline_payment.models.permit import Permit
from offline_payment.models.claim import Claim
from offline_payment.settlement.first_claim import FirstClaimSettlement
from offline_payment.settlement.pro_rata import GlobalProRataSettlement
from offline_payment.settlement.payer_liability import PayerLiabilitySettlement
from offline_payment.metrics.recovery import calculate_recovery_metrics
from offline_payment.metrics.attacker_profit import calculate_attacker_profit
from offline_payment.metrics.financial_loss import calculate_financial_loss
from offline_payment.metrics.telemetry import TelemetryLogger


COVERAGE_RATIOS = [0.10, 0.25, 0.50, 0.667, 0.75, 1.00, 1.25, 1.50]


def run_reserve_coverage_experiment(
    coverage_ratios: Optional[List[float]] = None,
    claim_amount_paise: int = 50000,
    num_claims: int = 3,
    output_dir: str = "results",
    logger: Optional[TelemetryLogger] = None,
) -> List[Dict]:
    """Run reserve coverage sensitivity sweep across all three policies."""
    if coverage_ratios is None:
        coverage_ratios = COVERAGE_RATIOS

    os.makedirs(output_dir, exist_ok=True)
    summary_csv = os.path.join(output_dir, "reserve_coverage_summary.csv")
    raw_csv = os.path.join(output_dir, "reserve_coverage_raw.csv")

    total_claims_x = claim_amount_paise * num_claims
    policies = [
        FirstClaimSettlement(),
        GlobalProRataSettlement(),
        PayerLiabilitySettlement(),
    ]

    summary_rows = []
    raw_rows = []

    for ratio in coverage_ratios:
        reserve_s = round(ratio * total_claims_x)

        # Funding breakdown: up to 50000 from C, next 50000 from H, rest from F
        c_val = min(reserve_s, claim_amount_paise)
        h_val = min(reserve_s - c_val, claim_amount_paise)
        f_val = reserve_s - c_val - h_val

        permit = Permit(
            permit_id="p_cov_1",
            allowance_id=f"alw_cov_{int(ratio*1000)}",
            payer_id="payer_cov",
            payer_public_key="pk_cov",
            denomination=claim_amount_paise,
            settlement_deadline=1000,
            issuer_signature="sig_root",
        )

        claims = [
            Claim(
                tx_uuid=f"tx_cov_{ratio}_{i}",
                allowance_id=permit.allowance_id,
                permit_id=permit.permit_id,
                payer_id=permit.payer_id,
                payee_id=f"mule_1" if i == 1 else f"merchant_{i}",
                amount=claim_amount_paise,
                ingestion_sequence=i,
                submission_time=1000 + i,
                claim_type=ClaimType.MULE if i == 1 else ClaimType.HONEST_MERCHANT,
            )
            for i in range(1, num_claims + 1)
        ]

        for policy in policies:
            allowance = Allowance(
                allowance_id=permit.allowance_id,
                payer_id=permit.payer_id,
                allowance_amount=c_val,
                payer_hold=h_val,
                issuer_guarantee=f_val,
                settlement_deadline=1000,
                permits=[permit],
            )

            res = policy.settle(allowance, claims)
            if logger is not None:
                logger.record_settlement(
                    experiment_name=f"coverage_{ratio}",
                    allowance=allowance,
                    batch_result=res,
                    payer_is_attacker=True,
                    attack_costs_paise=0,
                )
            rec = calculate_recovery_metrics(res)
            prof = calculate_attacker_profit(res, attack_costs=0, payer_is_attacker=True)
            loss = calculate_financial_loss(res)

            summary_rows.append({
                "coverage_ratio": ratio,
                "total_claims_count": res.total_claims_count,
                "eligible_claims_count": res.total_eligible_count,
                "total_claims_x_paise": total_claims_x,
                "reserve_s_paise": reserve_s,
                "policy": policy.policy_type.value,
                "total_payout_paise": res.total_payout,
                "total_payout_inr": f"{res.total_payout / PAISE_PER_INR:.2f}",
                "overall_recovery_rate": f"{rec.overall_recovery_rate:.4f}" if rec.overall_recovery_rate is not None else "N/A",
                "honest_recovery_rate": f"{rec.honest_recovery_rate:.4f}" if rec.honest_recovery_rate is not None else "N/A",
                "mule_recovery_rate": f"{rec.mule_recovery_rate:.4f}" if rec.mule_recovery_rate is not None else "N/A",
                "honest_loss_paise": loss.honest_merchant_loss,
                "issuer_loss_paise": loss.issuer_loss,
                "payer_debit_paise": loss.payer_settled_debit,
                "attacker_profit_paise": prof.net_profit,
                "attacker_profit_inr": f"{prof.net_profit / PAISE_PER_INR:.2f}",
            })

            for cr in res.claim_results:
                raw_rows.append({
                    "coverage_ratio": ratio,
                    "policy": policy.policy_type.value,
                    "tx_uuid": cr.claim.tx_uuid,
                    "claim_type": cr.claim.claim_type.value,
                    "ingestion_sequence": cr.claim.ingestion_sequence,
                    "requested_amount_paise": cr.requested_amount,
                    "paid_amount_paise": cr.paid_amount,
                    "status": cr.status.value,
                    "funded_c_paise": cr.funded_from_c,
                    "funded_h_paise": cr.funded_from_h,
                    "funded_f_paise": cr.funded_from_f,
                })

    # Save CSVs
    with open(summary_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)

    with open(raw_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(raw_rows[0].keys()))
        writer.writeheader()
        writer.writerows(raw_rows)

    return summary_rows
