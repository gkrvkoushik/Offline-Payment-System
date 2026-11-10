"""Claim domain model representing an offline transaction redemption request."""

from dataclasses import dataclass
from offline_payment.config import ClaimType


@dataclass
class Claim:
    """Offline transaction claim submitted for settlement.

    All monetary amounts are denominated in integer paise.
    Notice: claim_type is simulation ground truth only (e.g., honest merchant, mule).
    It must NEVER be used to determine cryptographic validity or settlement eligibility.
    """
    tx_uuid: str
    allowance_id: str
    permit_id: str
    payer_id: str
    payee_id: str
    amount: int  # in paise
    ingestion_sequence: int
    submission_time: int
    payer_signature_valid: bool = True
    payee_signature_valid: bool = True
    issuer_signature_valid: bool = True
    claim_type: ClaimType = ClaimType.HONEST_MERCHANT
    offline_accepted: bool = True  # Receiver accepted the offline transaction and released goods
    pos_validation_passed: bool = True  # Verified format & signatures at POS
    goods_released: bool = True         # Physical goods/services released at POS
    attacker_id: str = "attacker_001"
    attacker_controls_payer: bool = False
    attacker_controls_payee: bool = False
    payer_is_victim: bool = False
    attack_costs_paise: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.amount, int) or self.amount <= 0:
            raise ValueError(f"Claim amount must be a positive integer in paise, got {self.amount}")
        if not isinstance(self.ingestion_sequence, int) or self.ingestion_sequence < 0:
            raise ValueError(f"Ingestion sequence must be a non-negative integer, got {self.ingestion_sequence}")

    @property
    def is_cryptographically_valid(self) -> bool:
        """Verify that all digital signatures (issuer, payer, payee) are valid."""
        return (
            self.payer_signature_valid
            and self.payee_signature_valid
            and self.issuer_signature_valid
        )

    def qualifies_for_goods_acquired(self, centre_validation_passed: bool = True) -> bool:
        """Determine whether physical goods/services were acquired at POS for this claim.

        Requires:
        1. offline_accepted == True (Receiver accepted the offline transaction)
        2. pos_validation_passed == True (Verified format & signatures at POS terminal)
        3. goods_released == True (Physical goods/services surrendered to customer)
        4. is_cryptographically_valid == True (Valid issuer, payer, and payee signatures)
        5. centre_validation_passed == True (Centre-side structural validation succeeded)
        6. Payee is NOT attacker-controlled and claim is NOT a mule/self claim.
        """
        is_attacker_payee = (
            self.attacker_controls_payee
            or self.claim_type in (ClaimType.MULE, ClaimType.ATTACKER_SELF)
        )
        if is_attacker_payee:
            return False

        return (
            bool(self.offline_accepted)
            and bool(self.pos_validation_passed)
            and bool(self.goods_released)
            and bool(self.is_cryptographically_valid)
            and bool(centre_validation_passed)
        )
