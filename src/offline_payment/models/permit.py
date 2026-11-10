"""Permit domain model representing single-use or fixed-denomination offline spending credentials."""

from dataclasses import dataclass
from offline_payment.config import PermitStatus


@dataclass
class Permit:
    """Offline spending permit.

    All denominations are denominated strictly in integer paise.
    """
    permit_id: str
    allowance_id: str
    payer_id: str
    payer_public_key: str
    denomination: int  # in paise
    settlement_deadline: int
    issuer_signature: str
    status: PermitStatus = PermitStatus.ACTIVE

    def __post_init__(self) -> None:
        if not isinstance(self.denomination, int) or self.denomination <= 0:
            raise ValueError(f"Denomination must be a positive integer in paise, got {self.denomination}")
