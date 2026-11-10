"""Self-claim attack scenario generator.

Attacker spends offline at honest merchants and also submits a self-claim
to their own payee account to cannibalize available reserve.
"""

from typing import List
from offline_payment.config import ClaimType
from offline_payment.models.allowance import Allowance
from offline_payment.models.claim import Claim
from offline_payment.models.permit import Permit


def generate_self_claim_scenario(
    allowance: Allowance,
    permits: List[Permit],
    num_honest_merchants: int = 2,
    claim_amount: int = 50000,
    self_claim_first: bool = True,
) -> List[Claim]:
    """Generate scenario with both honest merchant claims and attacker self-redemption claims."""
    claims: List[Claim] = []
    seq = 1

    if self_claim_first:
        # Attacker submits self-claim first
        claims.append(
            Claim(
                tx_uuid=f"tx_self_{allowance.allowance_id}_0",
                allowance_id=allowance.allowance_id,
                permit_id=permits[0].permit_id,
                payer_id=allowance.payer_id,
                payee_id="attacker_self_account",
                amount=claim_amount,
                ingestion_sequence=seq,
                submission_time=1000 + seq,
                claim_type=ClaimType.ATTACKER_SELF,
            )
        )
        seq += 1

    for i in range(1, num_honest_merchants + 1):
        permit = permits[0] if len(permits) == 1 else permits[min(i, len(permits) - 1)]
        claims.append(
            Claim(
                tx_uuid=f"tx_honest_{allowance.allowance_id}_{i}",
                allowance_id=allowance.allowance_id,
                permit_id=permit.permit_id,
                payer_id=allowance.payer_id,
                payee_id=f"merchant_{i}",
                amount=claim_amount,
                ingestion_sequence=seq,
                submission_time=1000 + seq,
                claim_type=ClaimType.HONEST_MERCHANT,
            )
        )
        seq += 1

    if not self_claim_first:
        # Attacker submits self-claim after honest claims
        claims.append(
            Claim(
                tx_uuid=f"tx_self_{allowance.allowance_id}_end",
                allowance_id=allowance.allowance_id,
                permit_id=permits[0].permit_id,
                payer_id=allowance.payer_id,
                payee_id="attacker_self_account",
                amount=claim_amount,
                ingestion_sequence=seq,
                submission_time=1000 + seq,
                claim_type=ClaimType.ATTACKER_SELF,
            )
        )

    return claims
