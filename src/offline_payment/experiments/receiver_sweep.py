"""Experiment: Receiver count, mule share, and position sweep."""

from typing import Dict, List, Literal, Optional
import csv
import os

from offline_payment.config import PAISE_PER_INR
from offline_payment.models.allowance import Allowance
from offline_payment.models.permit import Permit
from offline_payment.settlement.first_claim import FirstClaimSettlement
from offline_payment.settlement.pro_rata import GlobalProRataSettlement
from offline_payment.settlement.payer_liability import PayerLiabilitySettlement
from offline_payment.attacks.mule_account import generate_mule_scenario
from offline_payment.metrics.recovery import calculate_recovery_metrics
from offline_payment.metrics.attacker_profit import calculate_attacker_profit
from offline_payment.metrics.financial_loss import calculate_financial_loss
from offline_payment.metrics.telemetry import TelemetryLogger

RECEIVER_COUNTS = [1, 2, 3, 5, 10, 20]
MULE_SHARES = [0, 10, 25, 50, 75, 100]
POSITIONS: List[Literal["first", "middle", "last"]] = ["first", "middle", "last"]


def run_receiver_sweep_experiment(
    receiver_counts: Optional[List[int]] = None,
    mule_shares: Optional[List[int]] = None,
    positions: Optional[List[Literal["first", "middle", "last"]]] = None,
    claim_amount_paise: int = 50000,
    output_dir: str = "results",
    logger: Optional[TelemetryLogger] = None,
) -> List[Dict]:
    """Sweep receiver count, mule percentage, and arrival positions.

    Generates unique allowance and permit IDs per experiment configuration to ensure
    claims pass structural and cryptographic validation while intentionally sharing a permit
    to model offline double-spending.
    """
    if receiver_counts is None:
        receiver_counts = RECEIVER_COUNTS
    if mule_shares is None:
        mule_shares = MULE_SHARES
    if positions is None:
        positions = POSITIONS

    os.makedirs(output_dir, exist_ok=True)
    summary_csv = os.path.join(output_dir, "receiver_sweep_summary.csv")
    raw_csv = os.path.join(output_dir, "receiver_sweep_raw.csv")

    policies = [
        FirstClaimSettlement(),
        GlobalProRataSettlement(),
        PayerLiabilitySettlement(),
    ]

    summary_rows = []
    raw_rows = []

    # Fixed base reserve S = ₹1,000 (100000 paise) backed by C=50000, H=50000, F=0
    c_paise = 50000
    h_paise = 50000
    f_paise = 0

    for n_rec in receiver_counts:
        for m_share in mule_shares:
            for pos in positions:
                # If mule share is 0% or 100%, position has identical semantics; avoid duplicate runs
                if (m_share == 0 or m_share == 100) and pos != "first":
                    continue

                allowance_id = f"alw_swp_{n_rec}_{m_share}_{pos}"
                permit_id = f"p_swp_{n_rec}_{m_share}_{pos}"

                permit = Permit(
                    permit_id=permit_id,
                    allowance_id=allowance_id,
                    payer_id="payer_swp",
                    payer_public_key="pk_swp",
                    denomination=claim_amount_paise,
                    settlement_deadline=1000,
                    issuer_signature="sig_root",
                )

                allowance = Allowance(
                    allowance_id=allowance_id,
                    payer_id="payer_swp",
                    allowance_amount=c_paise,
                    payer_hold=h_paise,
                    issuer_guarantee=f_paise,
                    settlement_deadline=1000,
                    permits=[permit],
                )

                claims = generate_mule_scenario(
                    allowance=allowance,
                    permits=[permit],
                    total_receivers=n_rec,
                    mule_share_pct=m_share,
                    mule_position=pos,
                    claim_amount=claim_amount_paise,
                    offline_accepted=True,
                )

                for policy in policies:
                    res = policy.settle(allowance, claims)
                    if logger is not None:
                        logger.record_settlement(
                            experiment_name=f"receiver_sweep_n{n_rec}_m{m_share}_{pos}",
                            allowance=allowance,
                            batch_result=res,
                            payer_is_attacker=True,
                            attack_costs_paise=0,
                        )
                    rec = calculate_recovery_metrics(res)
                    prof = calculate_attacker_profit(res, attack_costs=0, payer_is_attacker=True)
                    loss = calculate_financial_loss(res)

                    summary_rows.append({
                        "num_receivers": n_rec,
                        "mule_share_pct": m_share,
                        "mule_position": pos,
                        "policy": policy.policy_type.value,
                        "total_claims_count": res.total_claims_count,
                        "eligible_claims_count": res.total_eligible_count,
                        "total_requested_paise": res.total_requested_amount,
                        "total_eligible_paise": res.total_eligible_amount,
                        "total_payout_paise": res.total_payout,
                        "total_payout_inr": f"{res.total_payout / PAISE_PER_INR:.2f}",
                        "overall_recovery_rate": f"{rec.overall_recovery_rate:.4f}" if rec.overall_recovery_rate is not None else "N/A",
                        "honest_recovery_rate": f"{rec.honest_recovery_rate:.4f}" if rec.honest_recovery_rate is not None else "N/A",
                        "mule_recovery_rate": f"{rec.mule_recovery_rate:.4f}" if rec.mule_recovery_rate is not None else "N/A",
                        "honest_loss_paise": loss.honest_merchant_loss,
                        "payer_debit_paise": loss.payer_settled_debit,
                        "attacker_profit_paise": prof.net_profit,
                        "attacker_profit_inr": f"{prof.net_profit / PAISE_PER_INR:.2f}",
                    })

                    for cr in res.claim_results:
                        raw_rows.append({
                            "num_receivers": n_rec,
                            "mule_share_pct": m_share,
                            "mule_position": pos,
                            "policy": policy.policy_type.value,
                            "tx_uuid": cr.claim.tx_uuid,
                            "claim_type": cr.claim.claim_type.value,
                            "ingestion_sequence": cr.claim.ingestion_sequence,
                            "requested_paise": cr.requested_amount,
                            "paid_paise": cr.paid_amount,
                            "status": cr.status.value,
                            "validation_passed": cr.validation_passed,
                            "rejection_reason": cr.rejection_reason or "",
                        })

    with open(summary_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)

    with open(raw_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(raw_rows[0].keys()))
        writer.writeheader()
        writer.writerows(raw_rows)

    return summary_rows
