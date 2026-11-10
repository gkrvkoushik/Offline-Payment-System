"""Strategic claim ordering attack generator.

Evaluates how adversary manipulation of claim submission order impacts recovery and payouts.
"""

from typing import List, Literal
from offline_payment.models.claim import Claim


def permute_claim_ordering(
    claims: List[Claim],
    strategy: Literal["mule_first", "mule_last", "honest_first", "interleaved"],
) -> List[Claim]:
    """Reorder a list of claims according to an adversarial or cooperative submission strategy.

    Updates ingestion_sequence to match the new order.
    """
    mule_claims = [c for c in claims if c.claim_type.value in ("MULE", "ATTACKER_SELF")]
    honest_claims = [c for c in claims if c.claim_type.value == "HONEST_MERCHANT"]

    if strategy == "mule_first":
        ordered = mule_claims + honest_claims
    elif strategy == "mule_last":
        ordered = honest_claims + mule_claims
    elif strategy == "honest_first":
        ordered = honest_claims + mule_claims
    elif strategy == "interleaved":
        ordered = []
        i, j = 0, 0
        while i < len(mule_claims) or j < len(honest_claims):
            if i < len(mule_claims):
                ordered.append(mule_claims[i])
                i += 1
            if j < len(honest_claims):
                ordered.append(honest_claims[j])
                j += 1
    else:
        ordered = list(claims)

    # Re-assign ingestion sequence to match new arrival order
    resequenced: List[Claim] = []
    for idx, c in enumerate(ordered, start=1):
        resequenced.append(
            Claim(
                tx_uuid=c.tx_uuid,
                allowance_id=c.allowance_id,
                permit_id=c.permit_id,
                payer_id=c.payer_id,
                payee_id=c.payee_id,
                amount=c.amount,
                ingestion_sequence=idx,
                submission_time=1000 + idx,
                payer_signature_valid=c.payer_signature_valid,
                payee_signature_valid=c.payee_signature_valid,
                issuer_signature_valid=c.issuer_signature_valid,
                claim_type=c.claim_type,
            )
        )
    return resequenced
