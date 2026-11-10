"""Policy A: First Claim Wins (FC) settlement algorithm."""

from typing import List, Set
from offline_payment.config import SettlementPolicy, SettlementStatus
from offline_payment.models.allowance import Allowance
from offline_payment.models.claim import Claim
from offline_payment.settlement.base import (
    BaseSettlementPolicy,
    ClaimSettlementResult,
    SettlementBatchResult,
)
from offline_payment.validation.claim_validator import ClaimValidator


class FirstClaimSettlement(BaseSettlementPolicy):
    """First Claim Wins (FC).

    Accepts the first cryptographically valid claim referencing a permit.
    Rejects subsequent claims referencing the same permit as double-spending.
    Enforces total reserve constraint S = C + H + F.
    """

    @property
    def policy_type(self) -> SettlementPolicy:
        return SettlementPolicy.FIRST_CLAIM

    def settle(self, allowance: Allowance, claims: List[Claim]) -> SettlementBatchResult:
        validator = ClaimValidator(allowance)
        sorted_claims = sorted(claims, key=lambda c: c.ingestion_sequence)

        # Track reserve funding tiers
        c_rem = allowance.allowance_amount
        h_rem = allowance.payer_hold
        f_rem = allowance.issuer_guarantee
        s_rem = allowance.total_reserve

        claimed_permits: Set[str] = set()
        claim_results: List[ClaimSettlementResult] = []

        total_requested = sum(c.amount for c in sorted_claims)
        total_eligible = 0
        total_payout = 0
        total_from_c = 0
        total_from_h = 0
        total_from_f = 0
        eligible_count = 0

        for claim in sorted_claims:
            val_res = validator.validate_claim(claim)
            if not val_res.is_valid:
                claim_results.append(
                    ClaimSettlementResult(
                        claim=claim,
                        requested_amount=claim.amount,
                        paid_amount=0,
                        status=SettlementStatus.REJECTED,
                        rejection_reason=val_res.error_message,
                        validation_passed=False,
                        settlement_eligible=False,
                    )
                )
                continue

            # Eligible claim
            eligible_count += 1
            total_eligible += claim.amount

            # Check permit reuse
            if claim.permit_id in claimed_permits:
                claim_results.append(
                    ClaimSettlementResult(
                        claim=claim,
                        requested_amount=claim.amount,
                        paid_amount=0,
                        status=SettlementStatus.REJECTED,
                        rejection_reason=f"Permit {claim.permit_id} already claimed by an earlier transaction (double-spend)",
                        validation_passed=True,
                        settlement_eligible=False,
                    )
                )
                continue

            # First claim for this permit
            claimed_permits.add(claim.permit_id)

            if s_rem <= 0:
                claim_results.append(
                    ClaimSettlementResult(
                        claim=claim,
                        requested_amount=claim.amount,
                        paid_amount=0,
                        status=SettlementStatus.UNPAID,
                        rejection_reason="Settlement reserve pool exhausted",
                    )
                )
                continue

            payout = min(claim.amount, s_rem)

            from_c = min(payout, c_rem)
            from_h = min(payout - from_c, h_rem)
            from_f = payout - from_c - from_h

            c_rem -= from_c
            h_rem -= from_h
            f_rem -= from_f
            s_rem -= payout

            total_payout += payout
            total_from_c += from_c
            total_from_h += from_h
            total_from_f += from_f

            status = (
                SettlementStatus.SETTLED_FULL
                if payout == claim.amount
                else SettlementStatus.SETTLED_PARTIAL
            )

            claim_results.append(
                ClaimSettlementResult(
                    claim=claim,
                    requested_amount=claim.amount,
                    paid_amount=payout,
                    status=status,
                    funded_from_c=from_c,
                    funded_from_h=from_h,
                    funded_from_f=from_f,
                    rejection_reason="Partial payment due to reserve limit" if status == SettlementStatus.SETTLED_PARTIAL else None,
                )
            )

        return SettlementBatchResult(
            policy=self.policy_type,
            total_claims_count=len(sorted_claims),
            total_eligible_count=eligible_count,
            total_requested_amount=total_requested,
            total_eligible_amount=total_eligible,
            total_payout=total_payout,
            total_funded_c=total_from_c,
            total_funded_h=total_from_h,
            total_funded_f=total_from_f,
            remaining_reserve=s_rem,
            claim_results=claim_results,
        )
