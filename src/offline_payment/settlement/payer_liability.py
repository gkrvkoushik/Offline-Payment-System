"""Policy C: Payer-Liable Strict Prefix (PL) settlement algorithm."""

from typing import List
from offline_payment.config import SettlementPolicy, SettlementStatus
from offline_payment.models.allowance import Allowance
from offline_payment.models.claim import Claim
from offline_payment.settlement.base import (
    BaseSettlementPolicy,
    ClaimSettlementResult,
    SettlementBatchResult,
)
from offline_payment.validation.claim_validator import ClaimValidator


class PayerLiabilitySettlement(BaseSettlementPolicy):
    """Payer-Liable Strict Prefix Settlement (PL).

    Processes cryptographically eligible claims strictly in ascending ingestion sequence.
    Funding waterfall:
      1. Payer allowance commitment C
      2. Additional payer hold H
      3. Issuer guarantee fund F

    Strict prefix semantics:
      - Pay each claim in full or not at all (no partial payouts).
      - If a claim cannot be paid in full, stop processing the allowance immediately.
      - All subsequent claims remain unpaid, even if smaller in amount.
    """

    @property
    def policy_type(self) -> SettlementPolicy:
        return SettlementPolicy.PAYER_LIABILITY

    def settle(self, allowance: Allowance, claims: List[Claim]) -> SettlementBatchResult:
        validator = ClaimValidator(allowance)
        sorted_claims = sorted(claims, key=lambda c: c.ingestion_sequence)

        c_rem = allowance.allowance_amount
        h_rem = allowance.payer_hold
        f_rem = allowance.issuer_guarantee
        s_rem = allowance.total_reserve

        claim_results: List[ClaimSettlementResult] = []
        total_requested = sum(c.amount for c in sorted_claims)
        total_eligible = 0
        total_payout = 0
        total_from_c = 0
        total_from_h = 0
        total_from_f = 0
        eligible_count = 0

        halted = False

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

            if halted:
                claim_results.append(
                    ClaimSettlementResult(
                        claim=claim,
                        requested_amount=claim.amount,
                        paid_amount=0,
                        status=SettlementStatus.UNPAID,
                        rejection_reason="Prefix settlement halted: earlier claim could not be paid in full",
                    )
                )
                continue

            # Check if this claim can be paid in full
            if claim.amount <= s_rem:
                # Pay in full
                from_c = min(claim.amount, c_rem)
                from_h = min(claim.amount - from_c, h_rem)
                from_f = claim.amount - from_c - from_h

                c_rem -= from_c
                h_rem -= from_h
                f_rem -= from_f
                s_rem -= claim.amount

                total_payout += claim.amount
                total_from_c += from_c
                total_from_h += from_h
                total_from_f += from_f

                claim_results.append(
                    ClaimSettlementResult(
                        claim=claim,
                        requested_amount=claim.amount,
                        paid_amount=claim.amount,
                        status=SettlementStatus.SETTLED_FULL,
                        funded_from_c=from_c,
                        funded_from_h=from_h,
                        funded_from_f=from_f,
                    )
                )
            else:
                # Cannot pay in full -> halt processing immediately
                halted = True
                claim_results.append(
                    ClaimSettlementResult(
                        claim=claim,
                        requested_amount=claim.amount,
                        paid_amount=0,
                        status=SettlementStatus.UNPAID,
                        rejection_reason=f"Insufficient remaining reserve ({s_rem}) for full claim amount ({claim.amount}); settlement halted",
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
