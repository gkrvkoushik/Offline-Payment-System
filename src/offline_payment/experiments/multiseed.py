"""Multi-seed randomized experiment module for statistical policy comparison.

Evaluates how random arrival order jitter and receiver distributions impact
FC, PR, and PL policies across reproducible deterministic random seeds.
"""

from typing import Dict, List, Optional
import csv
import math
import os
import random

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


DEFAULT_SEEDS = [42, 101, 777, 1337, 2024, 9999, 54321, 123456, 314159, 888888]


def run_multiseed_experiment(
    seeds: Optional[List[int]] = None,
    total_receivers: int = 10,
    mule_share_pct: int = 30,  # 3 mules, 7 honest merchants
    claim_amount_paise: int = 20000,  # INR 200 per claim
    num_permits: int = 4,  # 4 permits x INR 250 = INR 1,000 total permit inventory
    permit_denom_paise: int = 25000,
    c_paise: int = 50000,
    h_paise: int = 50000,
    f_paise: int = 0,
    output_dir: str = "results",
    logger: Optional[TelemetryLogger] = None,
) -> List[Dict]:
    """Execute reproducible multi-seed simulation across policies with randomized arrival orders."""
    if seeds is None:
        seeds = DEFAULT_SEEDS

    os.makedirs(output_dir, exist_ok=True)
    seeds_csv = os.path.join(output_dir, "multiseed_seeds.csv")
    summary_csv = os.path.join(output_dir, "multiseed_summary.csv")
    raw_csv = os.path.join(output_dir, "multiseed_raw.csv")

    policies = [
        FirstClaimSettlement(),
        GlobalProRataSettlement(),
        PayerLiabilitySettlement(),
    ]

    raw_rows = []
    # Key: (policy) -> list of metric dicts
    policy_runs: Dict[str, List[Dict]] = {p.policy_type.value: [] for p in policies}

    for seed in seeds:
        rng = random.Random(seed)
        allowance_id = f"alw_seed_{seed}"

        # 1. Create fixed permit inventory (4 permits x INR 250 = INR 1,000)
        permits = [
            Permit(
                permit_id=f"p_seed_{seed}_{i}",
                allowance_id=allowance_id,
                payer_id="payer_seed",
                payer_public_key=f"pk_seed_{i}",
                denomination=permit_denom_paise,
                settlement_deadline=1000,
                issuer_signature=f"sig_{i}",
            )
            for i in range(1, num_permits + 1)
        ]

        # 2. Generate claim entities (3 mules, 7 honest merchants)
        num_mules = (total_receivers * mule_share_pct + 50) // 100
        receiver_pool = (
            [(ClaimType.MULE, f"mule_{i}") for i in range(1, num_mules + 1)]
            + [(ClaimType.HONEST_MERCHANT, f"merchant_{i}") for i in range(1, total_receivers - num_mules + 1)]
        )

        # Shuffle arrival order deterministically using rng
        shuffled_receivers = list(receiver_pool)
        rng.shuffle(shuffled_receivers)

        # Build claims
        base_claims: List[Claim] = []
        for idx, (c_type, payee) in enumerate(shuffled_receivers, start=1):
            # Target permit randomly selected from permit inventory to simulate double spending
            target_permit = permits[rng.randint(0, num_permits - 1)]
            base_claims.append(
                Claim(
                    tx_uuid=f"tx_seed_{seed}_{idx}",
                    allowance_id=allowance_id,
                    permit_id=target_permit.permit_id,
                    payer_id="payer_seed",
                    payee_id=payee,
                    amount=claim_amount_paise,
                    ingestion_sequence=idx,
                    submission_time=1000 + idx,
                    claim_type=c_type,
                    offline_accepted=True,
                )
            )

        # 3. Settle identically across FC, PR, PL
        for policy in policies:
            allowance = Allowance(
                allowance_id=allowance_id,
                payer_id="payer_seed",
                allowance_amount=c_paise,
                payer_hold=h_paise,
                issuer_guarantee=f_paise,
                settlement_deadline=1000,
                permits=permits,
            )

            res = policy.settle(allowance, base_claims)
            if logger is not None:
                logger.record_settlement(
                    experiment_name=f"multiseed_s{seed}",
                    allowance=allowance,
                    batch_result=res,
                    payer_is_attacker=True,
                    attack_costs_paise=0,
                )
            rec = calculate_recovery_metrics(res)
            prof = calculate_attacker_profit(res, attack_costs=0, payer_is_attacker=True)
            loss = calculate_financial_loss(res)

            mule_payout_paise = sum(cr.paid_amount for cr in res.claim_results if cr.claim.claim_type == ClaimType.MULE)
            honest_payout_paise = sum(cr.paid_amount for cr in res.claim_results if cr.claim.claim_type == ClaimType.HONEST_MERCHANT)
            num_honest = total_receivers - num_mules

            run_record = {
                "experiment_id": f"exp_seed_{seed}_{policy.policy_type.value}",
                "seed": seed,
                "policy": policy.policy_type.value,
                "total_receivers": total_receivers,
                "mule_receivers": num_mules,
                "honest_receivers": num_honest,
                "total_claim_value": res.total_requested_amount,
                "mule_payout": mule_payout_paise,
                "honest_payout": honest_payout_paise,
                "total_payout": res.total_payout,
                "honest_recovery_pct": round(rec.honest_recovery_rate * 100.0, 4) if rec.honest_recovery_rate is not None else 0.0,
                "attacker_gross_goods_value": prof.goods_acquired,
                "mule_credit_recovered": prof.recoverable_mule_credit,
                "payer_owned_debit": prof.payer_owned_debit,
                "attack_cost": prof.attack_costs,
                "attacker_net_profit": prof.net_profit,
                # Backward-compatible fields
                "total_claims": res.total_claims_count,
                "total_requested_paise": res.total_requested_amount,
                "total_payout_paise": res.total_payout,
                "honest_recovery_rate": rec.honest_recovery_rate if rec.honest_recovery_rate is not None else 0.0,
                "mule_recovery_rate": rec.mule_recovery_rate if rec.mule_recovery_rate is not None else 0.0,
                "overall_recovery_rate": rec.overall_recovery_rate if rec.overall_recovery_rate is not None else 0.0,
                "attacker_profit_paise": prof.net_profit,
                "payer_debit_paise": loss.payer_settled_debit,
                "issuer_loss_paise": loss.issuer_loss,
            }
            policy_runs[policy.policy_type.value].append(run_record)

            for cr in res.claim_results:
                raw_rows.append({
                    "seed": seed,
                    "policy": policy.policy_type.value,
                    "tx_uuid": cr.claim.tx_uuid,
                    "claim_type": cr.claim.claim_type.value,
                    "ingestion_sequence": cr.claim.ingestion_sequence,
                    "requested_paise": cr.requested_amount,
                    "paid_paise": cr.paid_amount,
                    "status": cr.status.value,
                    "validation_passed": cr.validation_passed,
                })

    # 4. Compute aggregated statistics across seeds
    summary_rows = []
    n_seeds = len(seeds)

    for pol_name, runs in policy_runs.items():
        mean_payout = sum(r["total_payout_paise"] for r in runs) / n_seeds
        mean_honest_rec = sum(r["honest_recovery_rate"] for r in runs) / n_seeds
        std_honest_rec = math.sqrt(sum((r["honest_recovery_rate"] - mean_honest_rec) ** 2 for r in runs) / n_seeds) if n_seeds > 1 else 0.0

        mean_mule_rec = sum(r["mule_recovery_rate"] for r in runs) / n_seeds
        std_mule_rec = math.sqrt(sum((r["mule_recovery_rate"] - mean_mule_rec) ** 2 for r in runs) / n_seeds) if n_seeds > 1 else 0.0

        mean_profit = sum(r["attacker_profit_paise"] for r in runs) / n_seeds
        std_profit = math.sqrt(sum((r["attacker_profit_paise"] - mean_profit) ** 2 for r in runs) / n_seeds) if n_seeds > 1 else 0.0

        summary_rows.append({
            "policy": pol_name,
            "seeds_count": n_seeds,
            "mean_payout_paise": round(mean_payout),
            "mean_payout_inr": f"{mean_payout / PAISE_PER_INR:.2f}",
            "mean_honest_recovery_rate": f"{mean_honest_rec:.4f}",
            "std_honest_recovery_rate": f"{std_honest_rec:.4f}",
            "mean_mule_recovery_rate": f"{mean_mule_rec:.4f}",
            "std_mule_recovery_rate": f"{std_mule_rec:.4f}",
            "mean_attacker_profit_paise": round(mean_profit),
            "mean_attacker_profit_inr": f"{mean_profit / PAISE_PER_INR:.2f}",
            "std_attacker_profit_paise": round(std_profit),
            "std_attacker_profit_inr": f"{std_profit / PAISE_PER_INR:.2f}",
        })

    # Write seed-level results CSV
    all_runs = []
    for runs in policy_runs.values():
        all_runs.extend(runs)
    if all_runs:
        with open(seeds_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(all_runs[0].keys()))
            writer.writeheader()
            writer.writerows(all_runs)

    # Write summary CSV
    with open(summary_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)

    # Write raw CSV
    with open(raw_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(raw_rows[0].keys()))
        writer.writeheader()
        writer.writerows(raw_rows)

    return summary_rows
