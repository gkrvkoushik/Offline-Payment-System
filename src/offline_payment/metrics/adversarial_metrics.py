"""Comprehensive metrics engine for adversarial settlement-policy evaluation.

Computes:
1. Honest recovery rate (honest payout / eligible honest claim value)
2. Attacker payout (disbursed to attacker-controlled receiving accounts)
3. Attacker profit (goods acquired + recoverable mule credit - payer debit - costs)
4. System shortfall (total eligible claims - total payout)
5. Reserve utilization (total payout / available reserve)
6. Mule advantage (attacker payout / total payout)
7. Order sensitivity (max metric across orders - min metric across orders)
8. Stranded reserve (unused reserve despite eligible unpaid claims)

Zero denominators are explicitly represented as None, avoiding fabricated values.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from offline_payment.config import ClaimType
from offline_payment.models.claim import Claim
from offline_payment.settlement.base import ClaimSettlementResult, SettlementBatchResult
from offline_payment.metrics.attacker_profit import is_claim_goods_acquired


@dataclass
class AdversarialRunMetrics:
    """Metrics calculated from a single settlement batch run."""

    # Primary identification
    policy: str
    scenario_id: str

    # Monetary aggregates (in integer paise)
    total_requested: int
    total_eligible: int
    total_payout: int
    system_shortfall: int
    available_reserve: int
    remaining_reserve: int
    stranded_reserve: int

    # Funding sources (in integer paise)
    funded_from_c: int
    funded_from_h: int
    funded_from_f: int
    payer_funded: int

    # Receiver class breakdowns (in integer paise)
    honest_eligible: int
    honest_payout: int
    honest_unpaid: int

    attacker_eligible: int
    attacker_payout: int
    attacker_unpaid: int

    # Economic payoff components (Explicit audit breakdown)
    goods_value_acquired: int
    mule_account_payout: int
    frozen_or_reversed_funds: int
    recoverable_mule_proceeds: int
    payer_owned_debit: int
    actual_attacker_costs: int
    net_economic_profit: int

    # Normalized ratios (None if zero-denominator)
    honest_recovery_rate: Optional[float]
    attacker_recovery_rate: Optional[float]
    reserve_utilization: Optional[float]
    mule_advantage: Optional[float]

    # Counts
    total_claims_count: int
    eligible_claims_count: int
    fully_settled_count: int
    partially_settled_count: int
    unpaid_count: int
    rejected_count: int

    # Aliases for backward compatibility
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
    def attacker_net_profit(self) -> int:
        return self.net_economic_profit

    def to_dict(self) -> Dict[str, Optional[float]]:
        """Return a dictionary representation with clean typing."""
        return {
            "policy": self.policy,
            "scenario_id": self.scenario_id,
            "total_requested_paise": self.total_requested,
            "total_eligible_paise": self.total_eligible,
            "total_payout_paise": self.total_payout,
            "system_shortfall_paise": self.system_shortfall,
            "available_reserve_paise": self.available_reserve,
            "remaining_reserve_paise": self.remaining_reserve,
            "stranded_reserve_paise": self.stranded_reserve,
            "funded_from_c_paise": self.funded_from_c,
            "funded_from_h_paise": self.funded_from_h,
            "funded_from_f_paise": self.funded_from_f,
            "payer_funded_paise": self.payer_funded,
            "honest_eligible_paise": self.honest_eligible,
            "honest_payout_paise": self.honest_payout,
            "honest_unpaid_paise": self.honest_unpaid,
            "attacker_eligible_paise": self.attacker_eligible,
            "attacker_payout_paise": self.attacker_payout,
            "attacker_unpaid_paise": self.attacker_unpaid,
            "goods_value_acquired_paise": self.goods_value_acquired,
            "mule_account_payout_paise": self.mule_account_payout,
            "frozen_or_reversed_funds_paise": self.frozen_or_reversed_funds,
            "recoverable_mule_proceeds_paise": self.recoverable_mule_proceeds,
            "payer_owned_debit_paise": self.payer_owned_debit,
            "actual_attacker_costs_paise": self.actual_attacker_costs,
            "net_economic_profit_paise": self.net_economic_profit,
            "honest_recovery_rate": self.honest_recovery_rate,
            "attacker_recovery_rate": self.attacker_recovery_rate,
            "reserve_utilization": self.reserve_utilization,
            "mule_advantage": self.mule_advantage,
            "total_claims_count": self.total_claims_count,
            "eligible_claims_count": self.eligible_claims_count,
            "fully_settled_count": self.fully_settled_count,
            "partially_settled_count": self.partially_settled_count,
            "unpaid_count": self.unpaid_count,
            "rejected_count": self.rejected_count,
        }


def calculate_adversarial_metrics(
    batch_result: SettlementBatchResult,
    scenario_id: str = "scenario_0",
    attack_costs_paise: int = 0,
    frozen_funds_paise: int = 0,
    payer_is_attacker: bool = True,
) -> AdversarialRunMetrics:
    """Compute complete quantitative metrics for an adversarial evaluation run.

    Explicitly models:
    - Goods value acquired at POS from honest merchants
    - Mule account payout disbursed by settlement
    - Recoverable mule proceeds after frozen/clawback deductions
    - Payer debits from payer-pledged balances (C + H)
    - Operational attack costs
    """
    honest_eligible = 0
    honest_payout = 0
    attacker_eligible = 0
    attacker_payout = 0

    goods_value_acquired = 0
    mule_account_payout = 0

    full_count = 0
    partial_count = 0
    unpaid_count = 0
    rejected_count = 0

    for cr in batch_result.claim_results:
        is_attacker_payee = (
            cr.claim.attacker_controls_payee
            or cr.claim.claim_type in (ClaimType.MULE, ClaimType.ATTACKER_SELF)
        )

        st_name = cr.status.name if hasattr(cr.status, "name") else str(cr.status)
        if "SETTLED_FULL" in st_name:
            full_count += 1
        elif "SETTLED_PARTIAL" in st_name:
            partial_count += 1
        elif "UNPAID" in st_name:
            unpaid_count += 1
        elif "REJECTED" in st_name:
            rejected_count += 1

        if is_attacker_payee:
            if cr.validation_passed:
                attacker_eligible += cr.requested_amount
                attacker_payout += cr.paid_amount
            mule_account_payout += cr.paid_amount
        else:
            if cr.validation_passed:
                honest_eligible += cr.requested_amount
                honest_payout += cr.paid_amount
            if is_claim_goods_acquired(cr.claim, centre_validation_passed=cr.validation_passed):
                goods_value_acquired += cr.requested_amount

    if not isinstance(attack_costs_paise, int) or attack_costs_paise < 0:
        raise ValueError(f"Attack costs must be a non-negative integer in paise, got {attack_costs_paise}")
    if not isinstance(frozen_funds_paise, int) or frozen_funds_paise < 0:
        raise ValueError(f"Frozen funds must be a non-negative integer in paise, got {frozen_funds_paise}")
    if frozen_funds_paise > mule_account_payout:
        raise ValueError(
            f"Frozen funds ({frozen_funds_paise} paise) cannot exceed total mule account payout ({mule_account_payout} paise)"
        )

    recoverable_mule_proceeds = mule_account_payout - frozen_funds_paise

    if payer_is_attacker:
        payer_owned_debit = batch_result.total_payer_funded
    else:
        payer_owned_debit = 0

    net_economic_profit = (goods_value_acquired + recoverable_mule_proceeds) - (
        payer_owned_debit + attack_costs_paise
    )

    system_shortfall = batch_result.total_eligible_amount - batch_result.total_payout
    available_reserve = batch_result.total_payout + batch_result.remaining_reserve
    stranded_reserve = batch_result.remaining_reserve if batch_result.unpaid_amount > 0 else 0

    honest_recovery_rate = (
        float(honest_payout) / float(honest_eligible) if honest_eligible > 0 else None
    )
    attacker_recovery_rate = (
        float(attacker_payout) / float(attacker_eligible) if attacker_eligible > 0 else None
    )
    reserve_utilization = (
        float(batch_result.total_payout) / float(available_reserve) if available_reserve > 0 else None
    )
    mule_advantage = (
        float(attacker_payout) / float(batch_result.total_payout) if batch_result.total_payout > 0 else None
    )

    return AdversarialRunMetrics(
        policy=batch_result.policy.name if hasattr(batch_result.policy, "name") else str(batch_result.policy),
        scenario_id=scenario_id,
        total_requested=batch_result.total_requested_amount,
        total_eligible=batch_result.total_eligible_amount,
        total_payout=batch_result.total_payout,
        system_shortfall=system_shortfall,
        available_reserve=available_reserve,
        remaining_reserve=batch_result.remaining_reserve,
        stranded_reserve=stranded_reserve,
        funded_from_c=batch_result.total_funded_c,
        funded_from_h=batch_result.total_funded_h,
        funded_from_f=batch_result.total_funded_f,
        payer_funded=batch_result.total_payer_funded,
        honest_eligible=honest_eligible,
        honest_payout=honest_payout,
        honest_unpaid=honest_eligible - honest_payout,
        attacker_eligible=attacker_eligible,
        attacker_payout=attacker_payout,
        attacker_unpaid=attacker_eligible - attacker_payout,
        goods_value_acquired=goods_value_acquired,
        mule_account_payout=mule_account_payout,
        frozen_or_reversed_funds=frozen_funds_paise,
        recoverable_mule_proceeds=recoverable_mule_proceeds,
        payer_owned_debit=payer_owned_debit,
        actual_attacker_costs=attack_costs_paise,
        net_economic_profit=net_economic_profit,
        honest_recovery_rate=honest_recovery_rate,
        attacker_recovery_rate=attacker_recovery_rate,
        reserve_utilization=reserve_utilization,
        mule_advantage=mule_advantage,
        total_claims_count=batch_result.total_claims_count,
        eligible_claims_count=batch_result.total_eligible_count,
        fully_settled_count=full_count,
        partially_settled_count=partial_count,
        unpaid_count=unpaid_count,
        rejected_count=rejected_count,
    )


def compute_order_sensitivity(metrics_list: List[AdversarialRunMetrics], metric_name: str) -> Optional[float]:
    """Calculate maximum value minus minimum value across ordering permutations."""
    values = [getattr(m, metric_name) for m in metrics_list if getattr(m, metric_name) is not None]
    if not values:
        return None
    return max(values) - min(values)
