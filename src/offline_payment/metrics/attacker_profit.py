"""Attacker economic payoff and net profit metrics.

Payoff formulation:
    Net Economic Profit = (Goods Value Acquired + Recoverable Mule Proceeds) - (Payer-Owned Debit + Actual Attacker Costs)

Separated Components:
1. Goods Value Acquired (G):
   Under the offline payment protocol, when the payer presents a valid signed permit
   and transaction voucher to an honest merchant at POS, the merchant verifies the
   cryptographic signature offline and releases physical goods/services immediately.
   Settlement occurs later asynchronously. Thus, goods/services are irrevocably transferred
   at POS upon offline acceptance, with economic value equal to the face value of the honest claim.
2. Mule-Account Payout (P_mule):
   Gross settlement payout disbursed by the clearinghouse into attacker-controlled mule accounts.
3. Frozen / Reversed Funds (F_frozen):
   Funds successfully held, frozen, or clawed back by the clearinghouse before mule cashout.
4. Recoverable Mule Proceeds (R_mule = P_mule - F_frozen):
   Actual cash/crypto successfully extracted by the attacker through mule accounts.
5. Payer-Owned Debit (D_payer):
   Actual funds drawn from the payer's pledged balances (C + H).
   CRITICAL: Issuer guarantee funds (F) are backstopped by the financial institution,
   NOT drawn from the payer account, and thus are NEVER counted as payer debit.
   - When payer_is_attacker is True (e.g. self-claim / default double-spending), payer debit reduces
     attacker profit.
   - When payer_is_attacker is False (e.g. cloned victim key / compromised account), the attacker
     incurs 0 payer debit because the victim bears the loss.
6. Actual Attacker Costs (C_attack):
   Operational expenditure incurred by the adversary (e.g. mule recruitment fees, hardware, bribes).
"""

from dataclasses import dataclass
from typing import Optional
from offline_payment.config import ClaimType
from offline_payment.models.claim import Claim
from offline_payment.settlement.base import SettlementBatchResult


def is_claim_goods_acquired(claim: Claim, centre_validation_passed: bool = True) -> bool:
    """Canonical unified accounting rule for offline POS physical goods acquisition.

    Requirements:
    1. offline_accepted == True (Receiver accepted the offline transaction)
    2. pos_validation_passed == True (Verified format & signatures at POS terminal)
    3. goods_released == True (Physical goods/services surrendered to customer)
    4. is_cryptographically_valid == True (Valid digital signatures)
    5. centre_validation_passed == True (Centre-side structural validation succeeded)
    6. Payee is NOT attacker-controlled and claim is NOT a mule/self claim.
    """
    return claim.qualifies_for_goods_acquired(centre_validation_passed=centre_validation_passed)


@dataclass
class AttackerPayoff:
    """Attacker economic profit breakdown in integer paise."""

    goods_value_acquired: int
    mule_account_payout: int
    frozen_or_reversed_funds: int
    recoverable_mule_proceeds: int
    payer_owned_debit: int
    actual_attacker_costs: int
    net_economic_profit: int
    payer_is_attacker: bool

    # Backward compatibility properties
    @property
    def goods_acquired(self) -> int:
        return self.goods_value_acquired

    @property
    def recoverable_mule_credit(self) -> int:
        return self.recoverable_mule_proceeds

    @property
    def attack_costs(self) -> int:
        return self.actual_attacker_costs

    @property
    def net_profit(self) -> int:
        return self.net_economic_profit


def calculate_attacker_profit(
    batch_result: SettlementBatchResult,
    attack_costs: int = 0,
    frozen_funds: int = 0,
    payer_is_attacker: bool = True,
) -> AttackerPayoff:
    """Calculate attacker net economic profit from settlement results.

    All monetary amounts are in integer paise.
    Prevents double-counting by strictly segregating:
    - Goods acquired (from honest merchant claims only, adhering to unified POS criteria)
    - Mule cash proceeds (from attacker-controlled payee payouts only)
    - Payer debits (from payer-owned C+H only; issuer guarantee F is never debited from payer)
    """
    if not isinstance(attack_costs, int) or attack_costs < 0:
        raise ValueError(f"Attack costs must be a non-negative integer in paise, got {attack_costs}")
    if not isinstance(frozen_funds, int) or frozen_funds < 0:
        raise ValueError(f"Frozen funds must be a non-negative integer in paise, got {frozen_funds}")

    goods_value_acquired = 0
    mule_account_payout = 0

    for cr in batch_result.claim_results:
        is_attacker_payee = (
            cr.claim.attacker_controls_payee
            or cr.claim.claim_type in (ClaimType.MULE, ClaimType.ATTACKER_SELF)
        )

        if is_attacker_payee:
            # Cash disbursed to mule account
            mule_account_payout += cr.paid_amount
        else:
            # Honest merchant claims accepted offline represent goods/services released at POS
            if is_claim_goods_acquired(cr.claim, centre_validation_passed=cr.validation_passed):
                goods_value_acquired += cr.requested_amount

    # Validate bounds: frozen funds cannot exceed gross mule account payout
    if frozen_funds > mule_account_payout:
        raise ValueError(
            f"Frozen funds ({frozen_funds} paise) cannot exceed total mule account payout ({mule_account_payout} paise)"
        )

    recoverable_mule_proceeds = mule_account_payout - frozen_funds

    # Payer debit is strictly C + H paid out (issuer guarantee F is NEVER payer debit)
    if payer_is_attacker:
        payer_owned_debit = batch_result.total_payer_funded
    else:
        # Victim's account was debited, attacker suffered zero debit
        payer_owned_debit = 0

    net_economic_profit = (goods_value_acquired + recoverable_mule_proceeds) - (
        payer_owned_debit + attack_costs
    )

    return AttackerPayoff(
        goods_value_acquired=goods_value_acquired,
        mule_account_payout=mule_account_payout,
        frozen_or_reversed_funds=frozen_funds,
        recoverable_mule_proceeds=recoverable_mule_proceeds,
        payer_owned_debit=payer_owned_debit,
        actual_attacker_costs=attack_costs,
        net_economic_profit=net_economic_profit,
        payer_is_attacker=payer_is_attacker,
    )
