"""Double spending attack scenario generator.

Attacker reuses the same permit across multiple merchants offline.
"""

from typing import List
from offline_payment.config import ClaimType
from offline_payment.models.allowance import Allowance
from offline_payment.models.claim import Claim
from offline_payment.models.permit import Permit


def generate_double_spend_scenario(
    allowance: Allowance,
    permit: Permit,
    num_merchants: int = 3,
    claim_amount: int = 50000,
    mule_first: bool = False,
) -> List[Claim]:
    """Generate a sequence of claims referencing the same permit.

    Args:
        allowance: Backing allowance
        permit: Single permit being double spent
        num_merchants: Number of merchants/claims
        claim_amount: Face amount of each claim in paise
        mule_first: If True, claim 1 is routed to a mule account
    """
    claims: List[Claim] = []
    for i in range(1, num_merchants + 1):
        is_mule = (i == 1 and mule_first)
        claim_type = ClaimType.MULE if is_mule else ClaimType.HONEST_MERCHANT
        payee_id = f"mule_{i}" if is_mule else f"merchant_{i}"

        claims.append(
            Claim(
                tx_uuid=f"tx_ds_{permit.permit_id}_{i}",
                allowance_id=allowance.allowance_id,
                permit_id=permit.permit_id,
                payer_id=allowance.payer_id,
                payee_id=payee_id,
                amount=claim_amount,
                ingestion_sequence=i,
                submission_time=1000 + i,
                claim_type=claim_type,
            )
        )
    return claims
