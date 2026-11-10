"""Financial loss and balance accounting across system stakeholders."""

from dataclasses import dataclass
from offline_payment.config import ClaimType
from offline_payment.settlement.base import SettlementBatchResult


@dataclass
class StakeholderFinancialLoss:
    """Financial impact breakdown across stakeholders in integer paise."""
    honest_merchant_loss: int  # Unpaid honest merchant claims
    issuer_loss: int           # Issuer guarantee funds disbursed (F)
    payer_settled_debit: int   # Payer commitment and hold consumed (C + H)
    total_unpaid_claims: int   # Total unpaid claims across all receivers

    @property
    def total_external_loss(self) -> int:
        """Net loss absorbed outside the payer (honest merchants + issuer)."""
        return self.honest_merchant_loss + self.issuer_loss


def calculate_financial_loss(batch_result: SettlementBatchResult) -> StakeholderFinancialLoss:
    """Compute financial loss distribution across stakeholders."""
    honest_requested = 0
    honest_payout = 0

    for cr in batch_result.claim_results:
        if cr.claim.claim_type == ClaimType.HONEST_MERCHANT and cr.claim.is_cryptographically_valid:
            honest_requested += cr.requested_amount
            honest_payout += cr.paid_amount

    honest_loss = honest_requested - honest_payout
    issuer_loss = batch_result.total_funded_f
    payer_debit = batch_result.total_payer_funded

    return StakeholderFinancialLoss(
        honest_merchant_loss=honest_loss,
        issuer_loss=issuer_loss,
        payer_settled_debit=payer_debit,
        total_unpaid_claims=batch_result.unpaid_amount,
    )
