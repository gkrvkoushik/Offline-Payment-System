"""Allowance domain model representing offline spending authorizations and reserve pools."""

from dataclasses import dataclass, field
from typing import List
from offline_payment.config import AllowanceStatus
from offline_payment.models.permit import Permit


@dataclass
class Allowance:
    """Offline spending allowance backed by a three-tier funding waterfall.

    Funding structure:
    - allowance_amount (C): Payer committed offline allowance.
    - payer_hold (H): Additional payer funds held for settlement liability.
    - issuer_guarantee (F): Issuer backstop guarantee fund.

    Total reserve S = C + H + F.
    All monetary amounts are denominated in integer paise.
    """
    allowance_id: str
    payer_id: str
    allowance_amount: int  # C (paise)
    payer_hold: int  # H (paise)
    issuer_guarantee: int  # F (paise)
    settlement_deadline: int
    permits: List[Permit] = field(default_factory=list)
    status: AllowanceStatus = AllowanceStatus.ACTIVE

    def __post_init__(self) -> None:
        if not isinstance(self.allowance_amount, int) or self.allowance_amount < 0:
            raise ValueError(f"allowance_amount (C) must be non-negative integer paise, got {self.allowance_amount}")
        if not isinstance(self.payer_hold, int) or self.payer_hold < 0:
            raise ValueError(f"payer_hold (H) must be non-negative integer paise, got {self.payer_hold}")
        if not isinstance(self.issuer_guarantee, int) or self.issuer_guarantee < 0:
            raise ValueError(f"issuer_guarantee (F) must be non-negative integer paise, got {self.issuer_guarantee}")

    @property
    def total_reserve(self) -> int:
        """Total settlement funding S = C + H + F in integer paise."""
        return self.allowance_amount + self.payer_hold + self.issuer_guarantee

    @property
    def total_payer_backing(self) -> int:
        """Total funds pledged by the payer = C + H in integer paise."""
        return self.allowance_amount + self.payer_hold
