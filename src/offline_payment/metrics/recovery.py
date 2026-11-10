"""Receiver recovery metrics and ratios for settlement evaluation."""

from dataclasses import dataclass
from typing import Optional
from offline_payment.config import ClaimType
from offline_payment.settlement.base import SettlementBatchResult


@dataclass
class RecoveryMetrics:
    """Quantitative recovery and distribution metrics across receiver classes.

    All absolute monetary values are in integer paise.
    Ratios are represented as floating-point fractions in [0.0, 1.0].
    """
    total_requested: int
    total_eligible: int
    total_payout: int
    unpaid_amount: int

    honest_requested: int
    honest_payout: int
    honest_recovery_rate: Optional[float]

    mule_requested: int
    mule_payout: int
    mule_recovery_rate: Optional[float]

    overall_recovery_rate: Optional[float]
    payer_funded_amount: int
    issuer_funded_amount: int
    stranded_reserve_amount: int


def calculate_recovery_metrics(batch_result: SettlementBatchResult) -> RecoveryMetrics:
    """Calculate comprehensive recovery metrics from a settlement batch result."""
    honest_requested = 0
    honest_payout = 0
    mule_requested = 0
    mule_payout = 0

    for cr in batch_result.claim_results:
        # Check claim type (ground truth)
        if cr.claim.claim_type == ClaimType.HONEST_MERCHANT:
            if cr.validation_passed:
                # Cryptographically and structurally eligible honest claims
                honest_requested += cr.requested_amount
                honest_payout += cr.paid_amount
        elif cr.claim.claim_type in (ClaimType.MULE, ClaimType.ATTACKER_SELF):
            if cr.validation_passed:
                mule_requested += cr.requested_amount
                mule_payout += cr.paid_amount

    overall_recovery = (
        float(batch_result.total_payout) / float(batch_result.total_eligible_amount)
        if batch_result.total_eligible_amount > 0
        else None
    )

    honest_recovery = (
        float(honest_payout) / float(honest_requested)
        if honest_requested > 0
        else None
    )

    mule_recovery = (
        float(mule_payout) / float(mule_requested)
        if mule_requested > 0
        else None
    )

    return RecoveryMetrics(
        total_requested=batch_result.total_requested_amount,
        total_eligible=batch_result.total_eligible_amount,
        total_payout=batch_result.total_payout,
        unpaid_amount=batch_result.unpaid_amount,
        honest_requested=honest_requested,
        honest_payout=honest_payout,
        honest_recovery_rate=honest_recovery,
        mule_requested=mule_requested,
        mule_payout=mule_payout,
        mule_recovery_rate=mule_recovery,
        overall_recovery_rate=overall_recovery,
        payer_funded_amount=batch_result.total_payer_funded,
        issuer_funded_amount=batch_result.total_funded_f,
        stranded_reserve_amount=batch_result.remaining_reserve,
    )
