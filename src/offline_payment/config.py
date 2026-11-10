"""Global configuration and constants for the offline payment simulator."""

from enum import Enum

# Currency unit conversions: 1 INR = 100 Paise
PAISE_PER_INR: int = 100


class AccountStatus(str, Enum):
    ACTIVE = "ACTIVE"
    FROZEN = "FROZEN"
    CLOSED = "CLOSED"


class AllowanceStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SETTLED = "SETTLED"
    EXPIRED = "EXPIRED"


class PermitStatus(str, Enum):
    ACTIVE = "ACTIVE"
    CONSUMED = "CONSUMED"
    EXPIRED = "EXPIRED"


class ClaimType(str, Enum):
    """Simulation ground truth only.

    Must NOT determine cryptographic validity or settlement eligibility.
    """
    HONEST_MERCHANT = "HONEST_MERCHANT"
    MULE = "MULE"
    ATTACKER_SELF = "ATTACKER_SELF"


class SettlementStatus(str, Enum):
    SETTLED_FULL = "SETTLED_FULL"
    SETTLED_PARTIAL = "SETTLED_PARTIAL"
    UNPAID = "UNPAID"
    REJECTED = "REJECTED"


class SettlementPolicy(str, Enum):
    FIRST_CLAIM = "FC"
    GLOBAL_PRO_RATA = "PR"
    PAYER_LIABILITY = "PL"
