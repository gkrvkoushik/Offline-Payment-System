"""Cloned key / credential theft attack scenario generator.

Attacker clones private spending keys of an honest victim and spends offline.
Crucially, the victim's account is debited during settlement, so payer_is_attacker is False.
"""

from typing import List
from offline_payment.config import ClaimType
from offline_payment.models.allowance import Allowance
from offline_payment.models.claim import Claim
from offline_payment.models.permit import Permit


def generate_cloned_key_scenario(
    victim_allowance: Allowance,
    permits: List[Permit],
    num_claims: int = 3,
    claim_amount: int = 50000,
    include_mule_drain: bool = True,
) -> List[Claim]:
    """Generate claims originating from cloned keys of a victim payer."""
    claims: List[Claim] = []
    seq = 1

    if include_mule_drain:
        # Attacker drains funds to mule first
        claims.append(
            Claim(
                tx_uuid=f"tx_cloned_{victim_allowance.allowance_id}_drain",
                allowance_id=victim_allowance.allowance_id,
                permit_id=permits[0].permit_id,
                payer_id=victim_allowance.payer_id,
                payee_id="attacker_mule_cashout",
                amount=claim_amount,
                ingestion_sequence=seq,
                submission_time=1000 + seq,
                claim_type=ClaimType.MULE,
            )
        )
        seq += 1

    for i in range(1, num_claims):
        permit = permits[min(i, len(permits) - 1)]
        claims.append(
            Claim(
                tx_uuid=f"tx_cloned_fraud_{victim_allowance.allowance_id}_{i}",
                allowance_id=victim_allowance.allowance_id,
                permit_id=permit.permit_id,
                payer_id=victim_allowance.payer_id,
                payee_id=f"merchant_victim_{i}",
                amount=claim_amount,
                ingestion_sequence=seq,
                submission_time=1000 + seq,
                claim_type=ClaimType.HONEST_MERCHANT,
            )
        )
        seq += 1

    return claims
