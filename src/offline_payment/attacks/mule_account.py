"""Mule account network attack generator.

Generates claim batches with controlled proportions and positions of mule accounts.
Uses a documented deterministic half-up integer rounding policy.
"""

from typing import List, Literal
from offline_payment.config import ClaimType
from offline_payment.models.allowance import Allowance
from offline_payment.models.claim import Claim
from offline_payment.models.permit import Permit


def calculate_mule_count(total_receivers: int, mule_share_pct: int) -> int:
    """Calculate the deterministic number of mule accounts using integer half-up rounding.

    Rounding Specification:
        Exact fraction = total_receivers * mule_share_pct / 100
        Deterministic half-up integer rounding: (total_receivers * mule_share_pct + 50) // 100
        Clamped to [0, total_receivers].

    Interpretation for small receiver counts (e.g., 1, 2, 3, 5):
        When a percentage cannot be exactly matched by an integer partition:
        - For total_receivers = 1:
            0% -> 0, 10% -> 0, 25% -> 0, 50% -> 1, 75% -> 1, 100% -> 1
        - For total_receivers = 2:
            0% -> 0, 10% -> 0, 25% -> 1, 50% -> 1, 75% -> 2, 100% -> 2
        - For total_receivers = 3:
            0% -> 0, 10% -> 0, 25% -> 1, 50% -> 2, 75% -> 2, 100% -> 3
        - For total_receivers = 5:
            0% -> 0, 10% -> 1, 25% -> 1, 50% -> 3, 75% -> 4, 100% -> 5

    This avoids Python's built-in round() which uses banker's rounding (round-half-to-even)
    and ensures strict reproducibility across platforms.
    """
    if total_receivers <= 0 or mule_share_pct <= 0:
        return 0
    if mule_share_pct >= 100:
        return total_receivers

    num_mules = (total_receivers * mule_share_pct + 50) // 100
    return min(total_receivers, max(0, num_mules))


def generate_mule_scenario(
    allowance: Allowance,
    permits: List[Permit],
    total_receivers: int = 4,
    mule_share_pct: int = 50,  # 0, 10, 25, 50, 75, 100
    mule_position: Literal["first", "middle", "last", "distributed"] = "first",
    claim_amount: int = 50000,
    offline_accepted: bool = True,
) -> List[Claim]:
    """Generate claim sets with designated mule receiver counts and positioning."""
    num_mules = calculate_mule_count(total_receivers, mule_share_pct)

    # Determine positions of mules
    mule_flags: List[bool] = [False] * total_receivers
    if num_mules > 0:
        if mule_position == "first":
            for i in range(num_mules):
                mule_flags[i] = True
        elif mule_position == "last":
            for i in range(total_receivers - num_mules, total_receivers):
                mule_flags[i] = True
        elif mule_position == "middle":
            start = (total_receivers - num_mules) // 2
            for i in range(start, start + num_mules):
                mule_flags[i] = True
        else:  # distributed
            step = total_receivers / num_mules
            for i in range(num_mules):
                idx = min(total_receivers - 1, int(i * step))
                mule_flags[idx] = True

    claims: List[Claim] = []
    permit_idx = 0

    for idx, is_mule in enumerate(mule_flags):
        permit = permits[permit_idx % len(permits)]
        permit_idx += 1

        seq = idx + 1
        claim_type = ClaimType.MULE if is_mule else ClaimType.HONEST_MERCHANT
        payee_id = f"mule_{seq}" if is_mule else f"merchant_{seq}"

        claims.append(
            Claim(
                tx_uuid=f"tx_mule_scen_{allowance.allowance_id}_{seq}",
                allowance_id=allowance.allowance_id,
                permit_id=permit.permit_id,
                payer_id=allowance.payer_id,
                payee_id=payee_id,
                amount=claim_amount,
                ingestion_sequence=seq,
                submission_time=1000 + seq,
                claim_type=claim_type,
                offline_accepted=offline_accepted,
            )
        )

    return claims
