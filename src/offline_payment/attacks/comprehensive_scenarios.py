"""Comprehensive attack scenarios with explicit ownership and attribution models."""

from typing import List, Tuple
from offline_payment.config import ClaimType
from offline_payment.models.allowance import Allowance
from offline_payment.models.claim import Claim
from offline_payment.models.permit import Permit


def build_scenario_malicious_payer_mule(
    allowance: Allowance,
    permit: Permit,
    claim_amount: int = 50000,
    mule_count: int = 2,
    attack_costs_paise: int = 0,
) -> List[Claim]:
    """Scenario 1: Malicious payer controls mule accounts to self-drain allowance.

    Attacker controls payer and payees. No goods released. Benefit is mule payout.
    """
    claims: List[Claim] = []
    for i in range(1, mule_count + 1):
        claims.append(
            Claim(
                tx_uuid=f"tx_mp_mule_{permit.permit_id}_{i}",
                allowance_id=allowance.allowance_id,
                permit_id=permit.permit_id,
                payer_id=allowance.payer_id,
                payee_id=f"attacker_mule_{i}",
                amount=claim_amount,
                ingestion_sequence=i,
                submission_time=1000 + i,
                claim_type=ClaimType.MULE,
                offline_accepted=True,
                pos_validation_passed=True,
                goods_released=False,
                attacker_id="attacker_alice",
                attacker_controls_payer=True,
                attacker_controls_payee=True,
                payer_is_victim=False,
                attack_costs_paise=attack_costs_paise,
            )
        )
    return claims


def build_scenario_malicious_payer_honest(
    allowance: Allowance,
    permit: Permit,
    merchant_count: int = 3,
    claim_amount: int = 50000,
    attack_costs_paise: int = 0,
) -> List[Claim]:
    """Scenario 2: Malicious payer attacks honest merchants with duplicate permits.

    Attacker controls payer, honest payees release goods at POS.
    """
    claims: List[Claim] = []
    for i in range(1, merchant_count + 1):
        claims.append(
            Claim(
                tx_uuid=f"tx_mp_honest_{permit.permit_id}_{i}",
                allowance_id=allowance.allowance_id,
                permit_id=permit.permit_id,
                payer_id=allowance.payer_id,
                payee_id=f"honest_merchant_{i}",
                amount=claim_amount,
                ingestion_sequence=i,
                submission_time=1000 + i,
                claim_type=ClaimType.HONEST_MERCHANT,
                offline_accepted=True,
                pos_validation_passed=True,
                goods_released=True,
                attacker_id="attacker_alice",
                attacker_controls_payer=True,
                attacker_controls_payee=False,
                payer_is_victim=False,
                attack_costs_paise=attack_costs_paise,
            )
        )
    return claims


def build_scenario_cloned_key_victim(
    victim_allowance: Allowance,
    permit: Permit,
    num_merchants: int = 2,
    claim_amount: int = 50000,
    attack_costs_paise: int = 2000,
) -> List[Claim]:
    """Scenario 3: Legitimate payer is victim of cloned credentials.

    Attacker uses cloned key of victim payer. Victim bears debit; attacker gets goods/credit.
    """
    claims: List[Claim] = []
    # 1. Attacker routes first claim to mule
    claims.append(
        Claim(
            tx_uuid=f"tx_cloned_mule_{victim_allowance.allowance_id}",
            allowance_id=victim_allowance.allowance_id,
            permit_id=permit.permit_id,
            payer_id=victim_allowance.payer_id,
            payee_id="attacker_cashout_mule",
            amount=claim_amount,
            ingestion_sequence=1,
            submission_time=1001,
            claim_type=ClaimType.MULE,
            offline_accepted=True,
            pos_validation_passed=True,
            goods_released=False,
            attacker_id="attacker_oscar",
            attacker_controls_payer=False,
            attacker_controls_payee=True,
            payer_is_victim=True,
            attack_costs_paise=attack_costs_paise,
        )
    )
    # 2. Attacker buys goods from honest merchants
    for i in range(1, num_merchants + 1):
        claims.append(
            Claim(
                tx_uuid=f"tx_cloned_honest_{victim_allowance.allowance_id}_{i}",
                allowance_id=victim_allowance.allowance_id,
                permit_id=permit.permit_id,
                payer_id=victim_allowance.payer_id,
                payee_id=f"honest_merchant_{i}",
                amount=claim_amount,
                ingestion_sequence=i + 1,
                submission_time=1001 + i,
                claim_type=ClaimType.HONEST_MERCHANT,
                offline_accepted=True,
                pos_validation_passed=True,
                goods_released=True,
                attacker_id="attacker_oscar",
                attacker_controls_payer=False,
                attacker_controls_payee=False,
                payer_is_victim=True,
                attack_costs_paise=0,
            )
        )
    return claims


def build_scenario_independent_mule(
    allowance: Allowance,
    permit: Permit,
    claim_amount: int = 50000,
    attack_costs_paise: int = 1000,
) -> List[Claim]:
    """Scenario 4: Independent mule account colluding to submit an invalid/replayed claim.

    Payer is legitimate, payee is independent mule attempting fraudulent redemption.
    """
    return [
        Claim(
            tx_uuid=f"tx_indep_mule_{permit.permit_id}_1",
            allowance_id=allowance.allowance_id,
            permit_id=permit.permit_id,
            payer_id=allowance.payer_id,
            payee_id="independent_mule_account",
            amount=claim_amount,
            ingestion_sequence=1,
            submission_time=1001,
            claim_type=ClaimType.MULE,
            offline_accepted=True,
            pos_validation_passed=True,
            goods_released=False,
            attacker_id="independent_mule_operator",
            attacker_controls_payer=False,
            attacker_controls_payee=True,
            payer_is_victim=False,
            attack_costs_paise=attack_costs_paise,
        ),
        Claim(
            tx_uuid=f"tx_indep_mule_{permit.permit_id}_2",
            allowance_id=allowance.allowance_id,
            permit_id=permit.permit_id,
            payer_id=allowance.payer_id,
            payee_id="honest_merchant_pos",
            amount=claim_amount,
            ingestion_sequence=2,
            submission_time=1002,
            claim_type=ClaimType.HONEST_MERCHANT,
            offline_accepted=True,
            pos_validation_passed=True,
            goods_released=True,
            attacker_id="independent_mule_operator",
            attacker_controls_payer=False,
            attacker_controls_payee=False,
            payer_is_victim=False,
            attack_costs_paise=0,
        ),
    ]


def build_scenario_mixed_honest_and_mule(
    allowance: Allowance,
    permit: Permit,
    claim_amount: int = 50000,
    attack_costs_paise: int = 0,
) -> List[Claim]:
    """Scenario 5: Mixed honest merchants and attacker-controlled mule account.

    Attacker controls payer and submits mule claim followed by honest merchant claims.
    """
    return [
        Claim(
            tx_uuid=f"tx_mixed_mule_{permit.permit_id}",
            allowance_id=allowance.allowance_id,
            permit_id=permit.permit_id,
            payer_id=allowance.payer_id,
            payee_id="attacker_mule_account",
            amount=claim_amount,
            ingestion_sequence=1,
            submission_time=1001,
            claim_type=ClaimType.MULE,
            offline_accepted=True,
            pos_validation_passed=True,
            goods_released=False,
            attacker_id="attacker_alice",
            attacker_controls_payer=True,
            attacker_controls_payee=True,
            payer_is_victim=False,
            attack_costs_paise=attack_costs_paise,
        ),
        Claim(
            tx_uuid=f"tx_mixed_merchant_a_{permit.permit_id}",
            allowance_id=allowance.allowance_id,
            permit_id=permit.permit_id,
            payer_id=allowance.payer_id,
            payee_id="merchant_alpha",
            amount=claim_amount,
            ingestion_sequence=2,
            submission_time=1002,
            claim_type=ClaimType.HONEST_MERCHANT,
            offline_accepted=True,
            pos_validation_passed=True,
            goods_released=True,
            attacker_id="attacker_alice",
            attacker_controls_payer=True,
            attacker_controls_payee=False,
            payer_is_victim=False,
            attack_costs_paise=0,
        ),
        Claim(
            tx_uuid=f"tx_mixed_merchant_b_{permit.permit_id}",
            allowance_id=allowance.allowance_id,
            permit_id=permit.permit_id,
            payer_id=allowance.payer_id,
            payee_id="merchant_beta",
            amount=claim_amount,
            ingestion_sequence=3,
            submission_time=1003,
            claim_type=ClaimType.HONEST_MERCHANT,
            offline_accepted=True,
            pos_validation_passed=True,
            goods_released=True,
            attacker_id="attacker_alice",
            attacker_controls_payer=True,
            attacker_controls_payee=False,
            payer_is_victim=False,
            attack_costs_paise=0,
        ),
    ]
