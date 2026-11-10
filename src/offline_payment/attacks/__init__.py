"""Attacks package for offline payment security evaluation."""

from offline_payment.attacks.double_spend import generate_double_spend_scenario
from offline_payment.attacks.self_claim import generate_self_claim_scenario
from offline_payment.attacks.mule_account import generate_mule_scenario, calculate_mule_count
from offline_payment.attacks.cloned_key import generate_cloned_key_scenario
from offline_payment.attacks.claim_ordering import permute_claim_ordering
from offline_payment.attacks.comprehensive_scenarios import (
    build_scenario_malicious_payer_mule,
    build_scenario_malicious_payer_honest,
    build_scenario_cloned_key_victim,
    build_scenario_independent_mule,
    build_scenario_mixed_honest_and_mule,
)

__all__ = [
    "generate_double_spend_scenario",
    "generate_self_claim_scenario",
    "generate_mule_scenario",
    "calculate_mule_count",
    "generate_cloned_key_scenario",
    "permute_claim_ordering",
    "build_scenario_malicious_payer_mule",
    "build_scenario_malicious_payer_honest",
    "build_scenario_cloned_key_victim",
    "build_scenario_independent_mule",
    "build_scenario_mixed_honest_and_mule",
]
