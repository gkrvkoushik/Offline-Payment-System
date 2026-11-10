"""Controlled scenario generator for adversarial settlement-policy evaluation.

Generates reproducible, serializable offline payment scenarios with explicit
parameterization of:
- Total eligible claim value (integer paise)
- Honest merchant count
- Attacker-controlled payee count (single vs distributed mule accounts)
- Mule claim share percentage
- Claim amounts and permit denominations
- Conflicting permit references (double-spending) vs distinct permits
- Funding tiers (C, H, F in integer paise)
- Ingestion order sequences
- Deterministic pseudo-random seeds
"""

import json
import random
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Literal, Optional, Tuple

from offline_payment.config import ClaimType, PermitStatus
from offline_payment.models.allowance import Allowance
from offline_payment.models.claim import Claim
from offline_payment.models.permit import Permit


@dataclass
class AdversarialScenario:
    """Serializable specification and instantiated models for an evaluation scenario."""

    scenario_id: str
    description: str
    allowance: Allowance
    claims: List[Claim]
    permit_conflict_type: Literal["same_permit", "distinct_permits"]
    mule_topology: Literal["single_mule", "multi_mule", "no_mule"]
    mule_share_pct: float
    reserve_ratio: float
    seed: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert scenario into a JSON-serializable dictionary."""
        return {
            "scenario_id": self.scenario_id,
            "description": self.description,
            "permit_conflict_type": self.permit_conflict_type,
            "mule_topology": self.mule_topology,
            "mule_share_pct": self.mule_share_pct,
            "reserve_ratio": self.reserve_ratio,
            "seed": self.seed,
            "metadata": self.metadata,
            "allowance": {
                "allowance_id": self.allowance.allowance_id,
                "payer_id": self.allowance.payer_id,
                "allowance_amount": self.allowance.allowance_amount,
                "payer_hold": self.allowance.payer_hold,
                "issuer_guarantee": self.allowance.issuer_guarantee,
                "total_reserve": self.allowance.total_reserve,
                "settlement_deadline": self.allowance.settlement_deadline,
                "permits": [
                    {
                        "permit_id": p.permit_id,
                        "denomination": p.denomination,
                        "payer_id": p.payer_id,
                    }
                    for p in self.allowance.permits
                ],
            },
            "claims": [
                {
                    "tx_uuid": c.tx_uuid,
                    "allowance_id": c.allowance_id,
                    "permit_id": c.permit_id,
                    "payer_id": c.payer_id,
                    "payee_id": c.payee_id,
                    "amount": c.amount,
                    "ingestion_sequence": c.ingestion_sequence,
                    "submission_time": c.submission_time,
                    "claim_type": c.claim_type.value,
                    "attacker_controls_payee": c.attacker_controls_payee,
                    "attacker_controls_payer": c.attacker_controls_payer,
                    "payer_is_victim": c.payer_is_victim,
                    "attack_costs_paise": c.attack_costs_paise,
                    "is_cryptographically_valid": c.is_cryptographically_valid,
                }
                for c in self.claims
            ],
        }

    def to_json(self, indent: int = 2) -> str:
        """Export scenario to formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def clone_with_order(self, order_indices: List[int], new_scenario_id: Optional[str] = None) -> "AdversarialScenario":
        """Create a deep copy with a newly specified claim ingestion order."""
        if len(order_indices) != len(self.claims):
            raise ValueError(f"Order indices length ({len(order_indices)}) must match claims count ({len(self.claims)})")

        reordered_claims = []
        for new_seq, orig_idx in enumerate(order_indices, start=1):
            orig_c = self.claims[orig_idx]
            reordered_c = Claim(
                tx_uuid=orig_c.tx_uuid,
                allowance_id=orig_c.allowance_id,
                permit_id=orig_c.permit_id,
                payer_id=orig_c.payer_id,
                payee_id=orig_c.payee_id,
                amount=orig_c.amount,
                ingestion_sequence=new_seq,
                submission_time=orig_c.submission_time + new_seq,
                payer_signature_valid=orig_c.payer_signature_valid,
                payee_signature_valid=orig_c.payee_signature_valid,
                issuer_signature_valid=orig_c.issuer_signature_valid,
                claim_type=orig_c.claim_type,
                offline_accepted=orig_c.offline_accepted,
                pos_validation_passed=orig_c.pos_validation_passed,
                goods_released=orig_c.goods_released,
                attacker_id=orig_c.attacker_id,
                attacker_controls_payer=orig_c.attacker_controls_payer,
                attacker_controls_payee=orig_c.attacker_controls_payee,
                payer_is_victim=orig_c.payer_is_victim,
                attack_costs_paise=orig_c.attack_costs_paise,
            )
            reordered_claims.append(reordered_c)

        return AdversarialScenario(
            scenario_id=new_scenario_id or f"{self.scenario_id}_reordered",
            description=f"{self.description} [order={order_indices}]",
            allowance=self.allowance,
            claims=reordered_claims,
            permit_conflict_type=self.permit_conflict_type,
            mule_topology=self.mule_topology,
            mule_share_pct=self.mule_share_pct,
            reserve_ratio=self.reserve_ratio,
            seed=self.seed,
            metadata={**self.metadata, "order_permutation": order_indices},
        )


class AdversarialScenarioGenerator:
    """Builder for generating rigorously parameterized offline payment scenarios."""

    def __init__(self, default_payer_id: str = "payer_alice", default_deadline: int = 1750000000):
        self.default_payer_id = default_payer_id
        self.default_deadline = default_deadline

    def generate_scenario(
        self,
        scenario_id: str,
        total_eligible_claim_value: int,  # in paise
        num_honest_merchants: int = 2,
        num_attacker_payees: int = 1,
        mule_claim_share: float = 0.3333333333333333,  # fraction in [0.0, 1.0]
        claim_amounts: Optional[List[int]] = None,
        permit_conflict: Literal["same_permit", "distinct_permits"] = "distinct_permits",
        available_c: int = 50000,
        available_h: int = 50000,
        available_f: int = 0,
        claim_ingestion_order: Optional[List[int]] = None,
        random_seed: Optional[int] = None,
        attacker_controls_payer: bool = True,
        attack_costs_paise: int = 0,
        description: str = "",
    ) -> AdversarialScenario:
        """Construct a validated, reproducible scenario."""
        if total_eligible_claim_value <= 0:
            raise ValueError(f"total_eligible_claim_value must be positive, got {total_eligible_claim_value}")
        if not (0.0 <= mule_claim_share <= 1.0):
            raise ValueError(f"mule_claim_share must be in [0.0, 1.0], got {mule_claim_share}")

        rng = random.Random(random_seed) if random_seed is not None else random.Random(42)

        total_reserve = available_c + available_h + available_f
        reserve_ratio = total_reserve / total_eligible_claim_value

        # Determine claim amounts
        if claim_amounts is not None:
            if sum(claim_amounts) != total_eligible_claim_value:
                raise ValueError(
                    f"Sum of explicit claim_amounts ({sum(claim_amounts)}) != total_eligible_claim_value ({total_eligible_claim_value})"
                )
            assigned_amounts = list(claim_amounts)
        else:
            # Deterministic integer division based on mule share
            total_mule_paise = round(total_eligible_claim_value * mule_claim_share)
            total_honest_paise = total_eligible_claim_value - total_mule_paise

            assigned_amounts = []
            # Divide mule claims across num_attacker_payees
            if num_attacker_payees > 0 and total_mule_paise > 0:
                base_mule = total_mule_paise // num_attacker_payees
                rem_mule = total_mule_paise % num_attacker_payees
                for i in range(num_attacker_payees):
                    assigned_amounts.append(base_mule + (1 if i < rem_mule else 0))

            # Divide honest claims across num_honest_merchants
            if num_honest_merchants > 0 and total_honest_paise > 0:
                base_honest = total_honest_paise // num_honest_merchants
                rem_honest = total_honest_paise % num_honest_merchants
                for i in range(num_honest_merchants):
                    assigned_amounts.append(base_honest + (1 if i < rem_honest else 0))

        # Classify each claim: attacker mule vs honest merchant
        actual_mule_count = num_attacker_payees if mule_claim_share > 0 else 0
        actual_honest_count = len(assigned_amounts) - actual_mule_count

        if actual_mule_count == 0:
            mule_topology = "no_mule"
        elif actual_mule_count == 1:
            mule_topology = "single_mule"
        else:
            mule_topology = "multi_mule"

        # Generate permits
        alw_id = f"alw_{scenario_id}"
        permits: List[Permit] = []

        if permit_conflict == "same_permit":
            # Single shared permit (Case A: double spend conflict)
            shared_permit = Permit(
                permit_id=f"p_shared_{scenario_id}",
                allowance_id=alw_id,
                payer_id=self.default_payer_id,
                payer_public_key=f"pk_{self.default_payer_id}",
                denomination=max(assigned_amounts),
                settlement_deadline=self.default_deadline,
                issuer_signature=f"sig_root_{scenario_id}",
                status=PermitStatus.ACTIVE,
            )
            permits.append(shared_permit)
        else:
            # Distinct permits for each claim (Case B: independent permits)
            for idx, amt in enumerate(assigned_amounts):
                permits.append(
                    Permit(
                        permit_id=f"p_{scenario_id}_{idx+1}",
                        allowance_id=alw_id,
                        payer_id=self.default_payer_id,
                        payer_public_key=f"pk_{self.default_payer_id}",
                        denomination=amt,
                        settlement_deadline=self.default_deadline,
                        issuer_signature=f"sig_root_{scenario_id}_{idx+1}",
                        status=PermitStatus.ACTIVE,
                    )
                )

        allowance = Allowance(
            allowance_id=alw_id,
            payer_id=self.default_payer_id,
            allowance_amount=available_c,
            payer_hold=available_h,
            issuer_guarantee=available_f,
            settlement_deadline=self.default_deadline,
            permits=permits,
        )

        # Build raw claims
        raw_claims: List[Claim] = []
        for idx, amt in enumerate(assigned_amounts):
            is_mule = idx < actual_mule_count
            if is_mule:
                payee_id = f"mule_acc_{idx+1}"
                ctype = ClaimType.MULE
                ctrl_payee = True
            else:
                h_idx = idx - actual_mule_count + 1
                payee_id = f"merchant_honest_{h_idx}"
                ctype = ClaimType.HONEST_MERCHANT
                ctrl_payee = False

            permit_ref = permits[0].permit_id if permit_conflict == "same_permit" else permits[idx].permit_id

            c = Claim(
                tx_uuid=f"tx_{scenario_id}_{idx+1}",
                allowance_id=alw_id,
                permit_id=permit_ref,
                payer_id=self.default_payer_id,
                payee_id=payee_id,
                amount=amt,
                ingestion_sequence=idx + 1,
                submission_time=1000 + idx,
                payer_signature_valid=True,
                payee_signature_valid=True,
                issuer_signature_valid=True,
                claim_type=ctype,
                offline_accepted=True,
                pos_validation_passed=True,
                goods_released=True,
                attacker_id="attacker_group_1" if ctrl_payee else "none",
                attacker_controls_payer=attacker_controls_payer,
                attacker_controls_payee=ctrl_payee,
                payer_is_victim=not attacker_controls_payer,
                attack_costs_paise=attack_costs_paise if is_mule else 0,
            )
            raw_claims.append(c)

        # Order assignment
        if claim_ingestion_order is not None:
            if len(claim_ingestion_order) != len(raw_claims):
                raise ValueError(
                    f"claim_ingestion_order length ({len(claim_ingestion_order)}) must equal claims count ({len(raw_claims)})"
                )
            final_claims = []
            for new_seq, orig_idx in enumerate(claim_ingestion_order, start=1):
                c = raw_claims[orig_idx]
                c.ingestion_sequence = new_seq
                final_claims.append(c)
        else:
            final_claims = raw_claims

        return AdversarialScenario(
            scenario_id=scenario_id,
            description=description or f"Scenario {scenario_id}: X={total_eligible_claim_value}, S={total_reserve}, rho={reserve_ratio:.2f}",
            allowance=allowance,
            claims=final_claims,
            permit_conflict_type=permit_conflict,
            mule_topology=mule_topology,
            mule_share_pct=mule_claim_share,
            reserve_ratio=reserve_ratio,
            seed=random_seed,
            metadata={
                "total_claims": len(final_claims),
                "mule_claims_count": actual_mule_count,
                "honest_claims_count": actual_honest_count,
                "c_paise": available_c,
                "h_paise": available_h,
                "f_paise": available_f,
            },
        )
