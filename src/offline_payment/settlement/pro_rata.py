"""Policy B: Global Pro-Rata (PR) settlement algorithm."""

from typing import Dict, List, Tuple
from offline_payment.config import SettlementPolicy, SettlementStatus
from offline_payment.models.allowance import Allowance
from offline_payment.models.claim import Claim
from offline_payment.settlement.base import (
    BaseSettlementPolicy,
    ClaimSettlementResult,
    SettlementBatchResult,
)
from offline_payment.validation.claim_validator import ClaimValidator


class GlobalProRataSettlement(BaseSettlementPolicy):
    """Global Pro-Rata Settlement (PR).

    Distributes pooled reserve S = C + H + F proportionally across all eligible claims.
    Uses the deterministic Largest-Remainder Method (Hare-Niemeyer method) for integer paise.
    Ties in remainder are broken using the earliest ingestion sequence.
    """

    @property
    def policy_type(self) -> SettlementPolicy:
        return SettlementPolicy.GLOBAL_PRO_RATA

    def settle(self, allowance: Allowance, claims: List[Claim]) -> SettlementBatchResult:
        validator = ClaimValidator(allowance)
        sorted_claims = sorted(claims, key=lambda c: c.ingestion_sequence)

        claim_results_by_key: Dict[Tuple[str, int], ClaimSettlementResult] = {}
        eligible_claims: List[Claim] = []

        total_requested = sum(c.amount for c in sorted_claims)
        total_eligible = 0

        # 1. Validation phase
        for claim in sorted_claims:
            val_res = validator.validate_claim(claim)
            claim_key = (claim.tx_uuid, claim.ingestion_sequence)
            if not val_res.is_valid:
                claim_results_by_key[claim_key] = ClaimSettlementResult(
                    claim=claim,
                    requested_amount=claim.amount,
                    paid_amount=0,
                    status=SettlementStatus.REJECTED,
                    rejection_reason=val_res.error_message,
                    validation_passed=False,
                    settlement_eligible=False,
                )
            else:
                eligible_claims.append(claim)
                total_eligible += claim.amount

        s_total = allowance.total_reserve
        payouts: Dict[Tuple[str, int], int] = {}

        # 2. Allocation phase via Largest-Remainder Method
        if total_eligible == 0 or s_total == 0:
            for claim in eligible_claims:
                payouts[(claim.tx_uuid, claim.ingestion_sequence)] = 0
            actual_total_payout = 0
        elif total_eligible <= s_total:
            # Full coverage: reserve is sufficient for all claims
            for claim in eligible_claims:
                payouts[(claim.tx_uuid, claim.ingestion_sequence)] = claim.amount
            actual_total_payout = total_eligible
        else:
            # Over-subscribed claims (X > S): proportional integer allocation
            # Base integer paise and remainder for each claim
            remainders: List[Tuple[int, int, Tuple[str, int]]] = []  # (-remainder, ingestion_sequence, key)
            base_sum = 0

            for claim in eligible_claims:
                numerator = claim.amount * s_total
                base_paise = numerator // total_eligible
                remainder = numerator % total_eligible
                claim_key = (claim.tx_uuid, claim.ingestion_sequence)
                payouts[claim_key] = base_paise
                base_sum += base_paise
                # Negate remainder for descending sort
                remainders.append((-remainder, claim.ingestion_sequence, claim_key))

            # Distribute remaining paise to claims with largest remainders
            remaining_paise = s_total - base_sum
            remainders.sort()

            for i in range(remaining_paise):
                _, _, claim_key = remainders[i]
                payouts[claim_key] += 1

            actual_total_payout = s_total

        # 3. Funding waterfall assignment (C -> H -> F)
        c_rem = allowance.allowance_amount
        h_rem = allowance.payer_hold
        f_rem = allowance.issuer_guarantee

        total_from_c = 0
        total_from_h = 0
        total_from_f = 0

        for claim in eligible_claims:
            claim_key = (claim.tx_uuid, claim.ingestion_sequence)
            payout = payouts[claim_key]

            from_c = min(payout, c_rem)
            from_h = min(payout - from_c, h_rem)
            from_f = payout - from_c - from_h

            c_rem -= from_c
            h_rem -= from_h
            f_rem -= from_f

            total_from_c += from_c
            total_from_h += from_h
            total_from_f += from_f

            if payout == claim.amount:
                status = SettlementStatus.SETTLED_FULL
                reason = None
            elif payout > 0:
                status = SettlementStatus.SETTLED_PARTIAL
                reason = "Pro-rata proportional allocation"
            else:
                status = SettlementStatus.UNPAID
                reason = "Pro-rata zero payout due to exhausted reserve"

            claim_results_by_key[claim_key] = ClaimSettlementResult(
                claim=claim,
                requested_amount=claim.amount,
                paid_amount=payout,
                status=status,
                funded_from_c=from_c,
                funded_from_h=from_h,
                funded_from_f=from_f,
                rejection_reason=reason,
            )

        # Assemble results in original ingestion sequence
        ordered_results = [claim_results_by_key[(c.tx_uuid, c.ingestion_sequence)] for c in sorted_claims]

        return SettlementBatchResult(
            policy=self.policy_type,
            total_claims_count=len(sorted_claims),
            total_eligible_count=len(eligible_claims),
            total_requested_amount=total_requested,
            total_eligible_amount=total_eligible,
            total_payout=actual_total_payout,
            total_funded_c=total_from_c,
            total_funded_h=total_from_h,
            total_funded_f=total_from_f,
            remaining_reserve=allowance.total_reserve - actual_total_payout,
            claim_results=ordered_results,
        )
