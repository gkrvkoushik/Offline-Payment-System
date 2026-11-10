"""Experiment: Policy comparison under baseline double-spending scenario."""

from dataclasses import dataclass
from typing import Dict, List, Optional
import csv
import os

from offline_payment.config import ClaimType, PAISE_PER_INR, SettlementPolicy
from offline_payment.models.allowance import Allowance
from offline_payment.models.permit import Permit
from offline_payment.models.claim import Claim
from offline_payment.settlement.first_claim import FirstClaimSettlement
from offline_payment.settlement.pro_rata import GlobalProRataSettlement
from offline_payment.settlement.payer_liability import PayerLiabilitySettlement
from offline_payment.metrics.recovery import calculate_recovery_metrics, RecoveryMetrics
from offline_payment.metrics.attacker_profit import calculate_attacker_profit, AttackerPayoff
from offline_payment.metrics.telemetry import TelemetryLogger


@dataclass
class InitialExperimentOutcome:
    policy: str
    mule_payout_paise: int
    merchant_a_payout_paise: int
    merchant_b_payout_paise: int
    total_payout_paise: int
    honest_recovery_rate: Optional[float]
    attacker_net_profit_paise: int
    total_claims_count: int = 3
    eligible_claims_count: int = 3

    @property
    def mule_payout_inr(self) -> float:
        return self.mule_payout_paise / PAISE_PER_INR

    @property
    def merchant_a_inr(self) -> float:
        return self.merchant_a_payout_paise / PAISE_PER_INR

    @property
    def merchant_b_inr(self) -> float:
        return self.merchant_b_payout_paise / PAISE_PER_INR

    @property
    def total_payout_inr(self) -> float:
        return self.total_payout_paise / PAISE_PER_INR

    @property
    def attacker_profit_inr(self) -> float:
        return self.attacker_net_profit_paise / PAISE_PER_INR


def run_initial_experiment(
    c_inr: int = 500,
    h_inr: int = 500,
    f_inr: int = 0,
    permit_denom_inr: int = 500,
    claim_amount_inr: int = 500,
    output_csv_path: Optional[str] = None,
    logger: Optional["TelemetryLogger"] = None,
) -> Dict[str, InitialExperimentOutcome]:
    """Execute the baseline reproducible experiment across FC, PR, and PL.

    Scenario:
      C = ₹500, H = ₹500, F = ₹0 -> Total reserve S = ₹1,000 (100,000 paise).
      One permit of ₹500 (50,000 paise).
      3 claims of ₹500 each:
        1. Mule account (seq 1)
        2. Honest merchant A (seq 2)
        3. Honest merchant B (seq 3)
      Total claims = ₹1,500 (150,000 paise).
    """
    c_paise = c_inr * PAISE_PER_INR
    h_paise = h_inr * PAISE_PER_INR
    f_paise = f_inr * PAISE_PER_INR
    denom_paise = permit_denom_inr * PAISE_PER_INR
    amount_paise = claim_amount_inr * PAISE_PER_INR

    # Set up models
    permit = Permit(
        permit_id="permit_001",
        allowance_id="alw_base",
        payer_id="payer_alice",
        payer_public_key="pubkey_alice",
        denomination=denom_paise,
        settlement_deadline=1700000000,
        issuer_signature="sig_issuer_root",
    )

    allowance = Allowance(
        allowance_id="alw_base",
        payer_id="payer_alice",
        allowance_amount=c_paise,
        payer_hold=h_paise,
        issuer_guarantee=f_paise,
        settlement_deadline=1700000000,
        permits=[permit],
    )

    # Identical claims for all three policies
    claims = [
        Claim(
            tx_uuid="tx_001_mule",
            allowance_id="alw_base",
            permit_id="permit_001",
            payer_id="payer_alice",
            payee_id="mule_charlie",
            amount=amount_paise,
            ingestion_sequence=1,
            submission_time=1001,
            claim_type=ClaimType.MULE,
        ),
        Claim(
            tx_uuid="tx_002_merchant_a",
            allowance_id="alw_base",
            permit_id="permit_001",
            payer_id="payer_alice",
            payee_id="merchant_a",
            amount=amount_paise,
            ingestion_sequence=2,
            submission_time=1002,
            claim_type=ClaimType.HONEST_MERCHANT,
        ),
        Claim(
            tx_uuid="tx_003_merchant_b",
            allowance_id="alw_base",
            permit_id="permit_001",
            payer_id="payer_alice",
            payee_id="merchant_b",
            amount=amount_paise,
            ingestion_sequence=3,
            submission_time=1003,
            claim_type=ClaimType.HONEST_MERCHANT,
        ),
    ]

    policies = [
        FirstClaimSettlement(),
        GlobalProRataSettlement(),
        PayerLiabilitySettlement(),
    ]

    outcomes: Dict[str, InitialExperimentOutcome] = {}
    csv_rows = []

    for policy in policies:
        # Clone allowance to avoid state contamination
        fresh_allowance = Allowance(
            allowance_id=allowance.allowance_id,
            payer_id=allowance.payer_id,
            allowance_amount=c_paise,
            payer_hold=h_paise,
            issuer_guarantee=f_paise,
            settlement_deadline=allowance.settlement_deadline,
            permits=[permit],
        )

        res = policy.settle(fresh_allowance, claims)
        if logger is not None:
            logger.record_settlement(
                experiment_name="initial_experiment",
                allowance=fresh_allowance,
                batch_result=res,
                payer_is_attacker=True,
                attack_costs_paise=0,
            )
        rec = calculate_recovery_metrics(res)
        prof = calculate_attacker_profit(res, attack_costs=0, payer_is_attacker=True)

        mule_p = res.claim_results[0].paid_amount
        m_a_p = res.claim_results[1].paid_amount
        m_b_p = res.claim_results[2].paid_amount

        outcome = InitialExperimentOutcome(
            policy=policy.policy_type.value,
            mule_payout_paise=mule_p,
            merchant_a_payout_paise=m_a_p,
            merchant_b_payout_paise=m_b_p,
            total_payout_paise=res.total_payout,
            honest_recovery_rate=rec.honest_recovery_rate,
            attacker_net_profit_paise=prof.net_profit,
            total_claims_count=res.total_claims_count,
            eligible_claims_count=res.total_eligible_count,
        )
        outcomes[policy.policy_type.value] = outcome

        csv_rows.append({
            "policy": outcome.policy,
            "total_claims_count": outcome.total_claims_count,
            "eligible_claims_count": outcome.eligible_claims_count,
            "mule_payout_paise": outcome.mule_payout_paise,
            "mule_payout_inr": f"{outcome.mule_payout_inr:.2f}",
            "merchant_a_payout_paise": outcome.merchant_a_payout_paise,
            "merchant_a_inr": f"{outcome.merchant_a_inr:.2f}",
            "merchant_b_payout_paise": outcome.merchant_b_payout_paise,
            "merchant_b_inr": f"{outcome.merchant_b_inr:.2f}",
            "total_payout_paise": outcome.total_payout_paise,
            "total_payout_inr": f"{outcome.total_payout_inr:.2f}",
            "honest_recovery_rate": f"{outcome.honest_recovery_rate:.4f}" if outcome.honest_recovery_rate is not None else "N/A",
            "attacker_profit_paise": outcome.attacker_net_profit_paise,
            "attacker_profit_inr": f"{outcome.attacker_profit_inr:.2f}",
        })

    if output_csv_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_csv_path)), exist_ok=True)
        with open(output_csv_path, mode="w", newline="", encoding="utf-8") as f:
            fieldnames = [
                "policy",
                "total_claims_count",
                "eligible_claims_count",
                "mule_payout_paise",
                "mule_payout_inr",
                "merchant_a_payout_paise",
                "merchant_a_inr",
                "merchant_b_payout_paise",
                "merchant_b_inr",
                "total_payout_paise",
                "total_payout_inr",
                "honest_recovery_rate",
                "attacker_profit_paise",
                "attacker_profit_inr",
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_rows)

    return outcomes
