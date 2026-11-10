"""Experiment: Denomination granularity under controlled economic demand.

Controlled design:
  - Fixed total allowance of INR 1,000 (100,000 paise) across all configurations.
  - Denomination configurations:
      * Micro: 10 permits x INR 100 (10,000 paise each) = INR 1,000 total.
      * Standard: 2 permits x INR 500 (50,000 paise each) = INR 1,000 total.
      * Large: 1 permit x INR 1,000 (100,000 paise) = INR 1,000 total.
  - Identical transaction demand (requested value, receivers, mule share, arrival patterns)
    tested across 7 distinct attack scenarios.
"""

from typing import Dict, List, Optional, Tuple
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


TOTAL_ALLOWANCE_PAISE = 1000 * PAISE_PER_INR  # INR 1,000 = 100,000 paise

FUNDING_CONFIGS = [
    {"name": "Balanced_Hold", "c_inr": 500, "h_inr": 500, "f_inr": 0},
    {"name": "Pure_Commitment", "c_inr": 1000, "h_inr": 0, "f_inr": 0},
    {"name": "Issuer_Backstop", "c_inr": 400, "h_inr": 200, "f_inr": 400},
]

DENOMINATION_CONFIGS = [
    {"name": "Micro", "count": 10, "denom_inr": 100, "denom_paise": 10000},
    {"name": "Standard", "count": 2, "denom_inr": 500, "denom_paise": 50000},
    {"name": "Large", "count": 1, "denom_inr": 1000, "denom_paise": 100000},
]

SCENARIO_NAMES = [
    "1_honest_spending",
    "2_single_permit_double_spend",
    "3_multi_permit_single_duplicate",
    "4_multi_permit_multi_duplicate",
    "5_mule_first",
    "6_mule_last",
    "7_varied_claim_sizes",
]


def create_controlled_permits(
    denom_config: Dict,
    allowance_id: str,
    payer_id: str = "payer_denom",
) -> List[Permit]:
    """Create permit inventory ensuring total permit value is invariant at exactly INR 1,000."""
    permits = []
    count = denom_config["count"]
    denom_paise = denom_config["denom_paise"]
    prefix = denom_config["name"].lower()

    for i in range(1, count + 1):
        permits.append(
            Permit(
                permit_id=f"p_{prefix}_{allowance_id}_{i}",
                allowance_id=allowance_id,
                payer_id=payer_id,
                payer_public_key=f"pk_{prefix}_{i}",
                denomination=denom_paise,
                settlement_deadline=1000,
                issuer_signature=f"sig_{prefix}_{i}",
            )
        )
    return permits


def generate_controlled_scenario_claims(
    scenario_name: str,
    denom_name: str,
    allowance_id: str,
    permits: List[Permit],
    payer_id: str = "payer_denom",
) -> List[Claim]:
    """Generate identical transaction demand across Micro, Standard, and Large configurations.

    Distinguishes requested claim amount from permit denomination.
    """
    claims: List[Claim] = []

    if scenario_name == "1_honest_spending":
        # Baseline honest spending: Total demand = INR 1,000 (100,000 paise).
        # No duplicates; each claim consumes a permit cleanly without double spending.
        if denom_name == "Micro":
            # 10 claims of INR 100 on 10 distinct permits
            for i in range(10):
                claims.append(
                    Claim(
                        tx_uuid=f"tx_{allowance_id}_honest_{i+1}",
                        allowance_id=allowance_id,
                        permit_id=permits[i].permit_id,
                        payer_id=payer_id,
                        payee_id=f"merchant_{i+1}",
                        amount=10000,
                        ingestion_sequence=i + 1,
                        submission_time=1000 + i + 1,
                        claim_type=ClaimType.HONEST_MERCHANT,
                    )
                )
        elif denom_name == "Standard":
            # 2 claims of INR 500 on 2 distinct permits
            for i in range(2):
                claims.append(
                    Claim(
                        tx_uuid=f"tx_{allowance_id}_honest_{i+1}",
                        allowance_id=allowance_id,
                        permit_id=permits[i].permit_id,
                        payer_id=payer_id,
                        payee_id=f"merchant_{i+1}",
                        amount=50000,
                        ingestion_sequence=i + 1,
                        submission_time=1000 + i + 1,
                        claim_type=ClaimType.HONEST_MERCHANT,
                    )
                )
        else:  # Large: 1 claim of INR 1,000 on 1 permit
            claims.append(
                Claim(
                    tx_uuid=f"tx_{allowance_id}_honest_1",
                    allowance_id=allowance_id,
                    permit_id=permits[0].permit_id,
                    payer_id=payer_id,
                    payee_id="merchant_1",
                    amount=100000,
                    ingestion_sequence=1,
                    submission_time=1001,
                    claim_type=ClaimType.HONEST_MERCHANT,
                )
            )

    elif scenario_name == "2_single_permit_double_spend":
        # Exactly 1 permit presented to 3 receivers (1 mule + 2 honest merchants).
        # Total demand = INR 300 (30,000 paise). Identical across Micro, Standard, Large.
        for seq, (c_type, payee) in enumerate([
            (ClaimType.MULE, "mule_1"),
            (ClaimType.HONEST_MERCHANT, "merchant_1"),
            (ClaimType.HONEST_MERCHANT, "merchant_2"),
        ], start=1):
            claims.append(
                Claim(
                    tx_uuid=f"tx_{allowance_id}_s2_{seq}",
                    allowance_id=allowance_id,
                    permit_id=permits[0].permit_id,  # All 3 target the first permit
                    payer_id=payer_id,
                    payee_id=payee,
                    amount=10000,  # INR 100 per claim
                    ingestion_sequence=seq,
                    submission_time=1000 + seq,
                    claim_type=c_type,
                )
            )

    elif scenario_name == "3_multi_permit_single_duplicate":
        # 11 claims of INR 100 = INR 1,100 total demand.
        # 1 mule (seq 1), 10 honest merchants (seq 2..11).
        # In Micro (10 permits): claims 1..10 use permits 0..9; claim 11 duplicates permit 0.
        # In Standard (2 permits): claims 1..6 on permit 0; claims 7..11 on permit 1.
        # In Large (1 permit): all 11 claims target permit 0.
        for seq in range(1, 12):
            is_mule = (seq == 1)
            c_type = ClaimType.MULE if is_mule else ClaimType.HONEST_MERCHANT
            payee = "mule_1" if is_mule else f"merchant_{seq-1}"

            if denom_name == "Micro":
                target_permit = permits[0] if seq == 11 else permits[seq - 1]
            elif denom_name == "Standard":
                target_permit = permits[0] if seq <= 6 else permits[1]
            else:
                target_permit = permits[0]

            claims.append(
                Claim(
                    tx_uuid=f"tx_{allowance_id}_s3_{seq}",
                    allowance_id=allowance_id,
                    permit_id=target_permit.permit_id,
                    payer_id=payer_id,
                    payee_id=payee,
                    amount=10000,
                    ingestion_sequence=seq,
                    submission_time=1000 + seq,
                    claim_type=c_type,
                )
            )

    elif scenario_name == "4_multi_permit_multi_duplicate":
        # 12 claims of INR 100 = INR 1,200 total demand.
        # 2 mules (seq 1, 2), 10 honest merchants (seq 3..12).
        # In Micro (10 permits): permits 0 and 1 are duplicated (claims 11 & 12); permits 2..9 are unique.
        # In Standard (2 permits): claims 1..6 on permit 0; claims 7..12 on permit 1.
        # In Large (1 permit): all 12 claims on permit 0.
        for seq in range(1, 13):
            is_mule = (seq in (1, 2))
            c_type = ClaimType.MULE if is_mule else ClaimType.HONEST_MERCHANT
            payee = f"mule_{seq}" if is_mule else f"merchant_{seq-2}"

            if denom_name == "Micro":
                if seq <= 10:
                    target_permit = permits[seq - 1]
                elif seq == 11:
                    target_permit = permits[0]  # duplicate permit 0
                else:
                    target_permit = permits[1]  # duplicate permit 1
            elif denom_name == "Standard":
                target_permit = permits[0] if seq <= 6 else permits[1]
            else:
                target_permit = permits[0]

            claims.append(
                Claim(
                    tx_uuid=f"tx_{allowance_id}_s4_{seq}",
                    allowance_id=allowance_id,
                    permit_id=target_permit.permit_id,
                    payer_id=payer_id,
                    payee_id=payee,
                    amount=10000,
                    ingestion_sequence=seq,
                    submission_time=1000 + seq,
                    claim_type=c_type,
                )
            )

    elif scenario_name == "5_mule_first":
        # 12 claims of INR 100 = INR 1,200 total demand.
        # 4 mules submitted FIRST (seq 1..4), 8 honest merchants LAST (seq 5..12).
        for seq in range(1, 13):
            is_mule = (seq <= 4)
            c_type = ClaimType.MULE if is_mule else ClaimType.HONEST_MERCHANT
            payee = f"mule_{seq}" if is_mule else f"merchant_{seq-4}"

            if denom_name == "Micro":
                target_permit = permits[seq - 1] if seq <= 10 else permits[seq - 11]
            elif denom_name == "Standard":
                target_permit = permits[0] if seq <= 6 else permits[1]
            else:
                target_permit = permits[0]

            claims.append(
                Claim(
                    tx_uuid=f"tx_{allowance_id}_s5_{seq}",
                    allowance_id=allowance_id,
                    permit_id=target_permit.permit_id,
                    payer_id=payer_id,
                    payee_id=payee,
                    amount=10000,
                    ingestion_sequence=seq,
                    submission_time=1000 + seq,
                    claim_type=c_type,
                )
            )

    elif scenario_name == "6_mule_last":
        # Identical 12 claims of INR 100, but 8 honest merchants arrive FIRST (seq 1..8),
        # and 4 mules arrive LAST (seq 9..12).
        for seq in range(1, 13):
            is_mule = (seq > 8)
            c_type = ClaimType.MULE if is_mule else ClaimType.HONEST_MERCHANT
            payee = f"mule_{seq-8}" if is_mule else f"merchant_{seq}"

            if denom_name == "Micro":
                target_permit = permits[seq - 1] if seq <= 10 else permits[seq - 11]
            elif denom_name == "Standard":
                target_permit = permits[0] if seq <= 6 else permits[1]
            else:
                target_permit = permits[0]

            claims.append(
                Claim(
                    tx_uuid=f"tx_{allowance_id}_s6_{seq}",
                    allowance_id=allowance_id,
                    permit_id=target_permit.permit_id,
                    payer_id=payer_id,
                    payee_id=payee,
                    amount=10000,
                    ingestion_sequence=seq,
                    submission_time=1000 + seq,
                    claim_type=c_type,
                )
            )

    elif scenario_name == "7_varied_claim_sizes":
        # 12 claims totaling exactly INR 1,000 (100,000 paise):
        # 4 small claims of INR 50 (5,000 paise) + 8 claims of INR 100 (10,000 paise).
        # Clearly demonstrates that claim amount != permit denomination.
        amounts = [5000, 5000, 5000, 5000] + [10000] * 8
        for seq, amt in enumerate(amounts, start=1):
            is_mule = (seq in (1, 2))
            c_type = ClaimType.MULE if is_mule else ClaimType.HONEST_MERCHANT
            payee = f"mule_{seq}" if is_mule else f"merchant_{seq-2}"

            if denom_name == "Micro":
                # Claims 1 & 2 on permit 0 (two 5000 claims)
                # Claims 3 & 4 on permit 1 (two 5000 claims)
                # Claims 5..12 on permits 2..9 (each 10000)
                if seq in (1, 2):
                    target_permit = permits[0]
                elif seq in (3, 4):
                    target_permit = permits[1]
                else:
                    target_permit = permits[seq - 3]
            elif denom_name == "Standard":
                target_permit = permits[0] if seq <= 6 else permits[1]
            else:
                target_permit = permits[0]

            claims.append(
                Claim(
                    tx_uuid=f"tx_{allowance_id}_s7_{seq}",
                    allowance_id=allowance_id,
                    permit_id=target_permit.permit_id,
                    payer_id=payer_id,
                    payee_id=payee,
                    amount=amt,
                    ingestion_sequence=seq,
                    submission_time=1000 + seq,
                    claim_type=c_type,
                )
            )

    return claims


def run_denomination_and_funding_experiment(
    funding_configs: Optional[List[Dict]] = None,
    denom_configs: Optional[List[Dict]] = None,
    scenario_names: Optional[List[str]] = None,
    output_dir: str = "results",
    logger: Optional[TelemetryLogger] = None,
) -> List[Dict]:
    """Execute controlled denomination granularity experiment.

    Keeps total allowance (INR 1,000), total permit value (INR 1,000), and transaction demand
    strictly invariant across Micro, Standard, and Large configurations.
    """
    if funding_configs is None:
        funding_configs = FUNDING_CONFIGS
    if denom_configs is None:
        denom_configs = DENOMINATION_CONFIGS
    if scenario_names is None:
        scenario_names = SCENARIO_NAMES

    os.makedirs(output_dir, exist_ok=True)
    summary_csv = os.path.join(output_dir, "denomination_summary.csv")
    raw_csv = os.path.join(output_dir, "denomination_raw.csv")

    policies = [
        FirstClaimSettlement(),
        GlobalProRataSettlement(),
        PayerLiabilitySettlement(),
    ]

    summary_rows = []
    raw_rows = []

    for s_name in scenario_names:
        for f_cfg in funding_configs:
            c_paise = f_cfg["c_inr"] * PAISE_PER_INR
            h_paise = f_cfg["h_inr"] * PAISE_PER_INR
            f_paise = f_cfg["f_inr"] * PAISE_PER_INR

            for d_cfg in denom_configs:
                denom_name = d_cfg["name"]
                allowance_id = f"alw_den_{s_name[:4]}_{f_cfg['name'][:4]}_{denom_name}"

                # 1. Create permits ensuring total permit value == 100,000 paise (INR 1,000)
                permits = create_controlled_permits(d_cfg, allowance_id)
                permit_map = {p.permit_id: p for p in permits}
                total_permit_value = sum(p.denomination for p in permits)
                assert total_permit_value == TOTAL_ALLOWANCE_PAISE, "Permit inventory value mismatch"

                # 2. Backing allowance with identical funding S = C + H + F = 100,000 paise
                allowance = Allowance(
                    allowance_id=allowance_id,
                    payer_id="payer_denom",
                    allowance_amount=c_paise,
                    payer_hold=h_paise,
                    issuer_guarantee=f_paise,
                    settlement_deadline=1000,
                    permits=permits,
                )

                # 3. Generate identical economic demand
                claims = generate_controlled_scenario_claims(
                    scenario_name=s_name,
                    denom_name=denom_name,
                    allowance_id=allowance_id,
                    permits=permits,
                )

                # 4. Settle identically across FC, PR, and PL
                for policy in policies:
                    res = policy.settle(allowance, claims)
                    if logger is not None:
                        logger.record_settlement(
                            experiment_name=f"denomination_{s_name}",
                            allowance=allowance,
                            batch_result=res,
                            payer_is_attacker=True,
                            attack_costs_paise=0,
                        )
                    rec = calculate_recovery_metrics(res)
                    prof = calculate_attacker_profit(res, attack_costs=0, payer_is_attacker=True)
                    loss = calculate_financial_loss(res)

                    # Stranded value = Total permit value (100,000) - Total payout
                    stranded_value_paise = TOTAL_ALLOWANCE_PAISE - res.total_payout

                    summary_rows.append({
                        "scenario_name": s_name,
                        "funding_config": f_cfg["name"],
                        "denomination_config": denom_name,
                        "policy": policy.policy_type.value,
                        "total_permits": len(permits),
                        "total_permit_value_paise": total_permit_value,
                        "total_permit_value_inr": f"{total_permit_value / PAISE_PER_INR:.2f}",
                        "total_requested_paise": res.total_requested_amount,
                        "total_requested_inr": f"{res.total_requested_amount / PAISE_PER_INR:.2f}",
                        "total_claims_count": res.total_claims_count,
                        "total_eligible_count": res.total_eligible_count,
                        "total_payout_paise": res.total_payout,
                        "total_payout_inr": f"{res.total_payout / PAISE_PER_INR:.2f}",
                        "overall_recovery_rate": f"{rec.overall_recovery_rate:.4f}" if rec.overall_recovery_rate is not None else "N/A",
                        "honest_recovery_rate": f"{rec.honest_recovery_rate:.4f}" if rec.honest_recovery_rate is not None else "N/A",
                        "mule_recovery_rate": f"{rec.mule_recovery_rate:.4f}" if rec.mule_recovery_rate is not None else "N/A",
                        "payer_debit_paise": loss.payer_settled_debit,
                        "issuer_loss_paise": loss.issuer_loss,
                        "attacker_profit_paise": prof.net_profit,
                        "attacker_profit_inr": f"{prof.net_profit / PAISE_PER_INR:.2f}",
                        "stranded_permit_value_paise": stranded_value_paise,
                        "stranded_permit_value_inr": f"{stranded_value_paise / PAISE_PER_INR:.2f}",
                    })

                    for cr in res.claim_results:
                        p = permit_map[cr.claim.permit_id]
                        raw_rows.append({
                            "scenario_name": s_name,
                            "funding_config": f_cfg["name"],
                            "denomination_config": denom_name,
                            "policy": policy.policy_type.value,
                            "allowance_id": cr.claim.allowance_id,
                            "permit_id": cr.claim.permit_id,
                            "denomination_paise": p.denomination,
                            "tx_uuid": cr.claim.tx_uuid,
                            "claim_type": cr.claim.claim_type.value,
                            "ingestion_sequence": cr.claim.ingestion_sequence,
                            "requested_paise": cr.requested_amount,
                            "paid_paise": cr.paid_amount,
                            "funded_c_paise": cr.funded_from_c,
                            "funded_h_paise": cr.funded_from_h,
                            "funded_f_paise": cr.funded_from_f,
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
