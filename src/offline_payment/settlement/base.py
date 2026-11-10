"""Base domain classes and interface for settlement policies."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
from offline_payment.config import SettlementPolicy, SettlementStatus
from offline_payment.models.allowance import Allowance
from offline_payment.models.claim import Claim


@dataclass
class ClaimSettlementResult:
    """Settlement outcome for a single transaction claim."""
    claim: Claim
    requested_amount: int  # in paise
    paid_amount: int  # in paise
    status: SettlementStatus
    funded_from_c: int = 0  # paise paid from payer commitment C
    funded_from_h: int = 0  # paise paid from payer hold H
    funded_from_f: int = 0  # paise paid from issuer guarantee F
    rejection_reason: Optional[str] = None
    validation_passed: bool = True  # Whether claim passed cryptographic and structural validation
    settlement_eligible: bool = True  # Whether eligible for settlement consideration under policy

    def __post_init__(self) -> None:
        if self.paid_amount < 0:
            raise ValueError(f"paid_amount cannot be negative: {self.paid_amount}")
        if self.paid_amount > self.requested_amount:
            raise ValueError(
                f"paid_amount ({self.paid_amount}) cannot exceed requested_amount ({self.requested_amount})"
            )
        if self.funded_from_c + self.funded_from_h + self.funded_from_f != self.paid_amount:
            raise ValueError(
                f"Sum of funding tiers ({self.funded_from_c} + {self.funded_from_h} + {self.funded_from_f}) "
                f"must equal paid_amount ({self.paid_amount})"
            )


@dataclass
class SettlementBatchResult:
    """Aggregated outcome of running a settlement policy over a claim batch."""
    policy: SettlementPolicy
    total_claims_count: int
    total_eligible_count: int
    total_requested_amount: int  # in paise (all submitted)
    total_eligible_amount: int   # in paise (cryptographically eligible)
    total_payout: int            # in paise
    total_funded_c: int          # in paise
    total_funded_h: int          # in paise
    total_funded_f: int          # in paise
    remaining_reserve: int       # in paise
    claim_results: List[ClaimSettlementResult]

    @property
    def unpaid_amount(self) -> int:
        """Unpaid portion of eligible claims."""
        return self.total_eligible_amount - self.total_payout

    @property
    def total_payer_funded(self) -> int:
        """Amount funded by payer-owned balances (C + H)."""
        return self.total_funded_c + self.total_funded_h


class BaseSettlementPolicy(ABC):
    """Abstract base class for all settlement policies."""

    @property
    @abstractmethod
    def policy_type(self) -> SettlementPolicy:
        """Settlement policy identifier."""
        pass

    @abstractmethod
    def settle(self, allowance: Allowance, claims: List[Claim]) -> SettlementBatchResult:
        """Execute settlement of claims against an allowance.

        Args:
            allowance: The backing allowance and reserve pool.
            claims: The batch of submitted claims.

        Returns:
            SettlementBatchResult with detailed breakdown.
        """
        pass
