"""Telemetry recording for complete permit inventory and attack event logging."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
import csv
import os

from offline_payment.config import ClaimType, PAISE_PER_INR, SettlementStatus
from offline_payment.models.allowance import Allowance
from offline_payment.models.permit import Permit
from offline_payment.settlement.base import SettlementBatchResult
from offline_payment.audit.audit_service import AuditSettlementPipeline
from offline_payment.blockchain.adapter import SimulatedEVMAdapter, BlockchainAdapter
from offline_payment.metrics.attacker_profit import is_claim_goods_acquired


@dataclass
class AuditAnchorRecord:
    """Record of a settlement batch Merkle root anchored to the blockchain."""
    experiment_name: str
    policy: str
    batch_id: str
    allowance_id: str
    event_count: int
    merkle_root: str
    tx_hash: str
    block_number: int
    gas_used: int
    status: str
    chain_id: int = 1337
    contract_address: str = "0x5FbDB2315678afecb367f032d93F642f64180aa3"
    contract_version: str = "1.0.0"
    transaction_hash: str = ""
    block_timestamp: int = 0
    receipt_status: str = "SIMULATED_MOCK_ANCHORED"
    confirmation_count: int = 1
    actual_gas_used: int = 44500
    anchor_attempts: int = 1
    execution_environment: str = "MOCK_SIMULATED_EVM"


@dataclass
class PermitInventoryRecord:
    """Record of an issued permit, including usage, pooled allocation, and stranded value."""
    allowance_id: str
    permit_id: str
    payer_id: str
    denomination_paise: int
    policy: str
    claims_count: int = 0
    conflicting_claims_count: int = 0
    total_claimed_paise: int = 0
    settlement_payout_attributed_paise: int = 0
    total_settled_paise: int = 0
    is_used: bool = False
    is_double_spent: bool = False
    unused_permit_value_released_paise: int = 0
    stranded_paise: int = 0
    permit_status: str = "UNUSED"

    @property
    def denomination_inr(self) -> float:
        return self.denomination_paise / PAISE_PER_INR

    @property
    def total_claimed_inr(self) -> float:
        return self.total_claimed_paise / PAISE_PER_INR

    @property
    def settlement_payout_attributed_inr(self) -> float:
        return self.settlement_payout_attributed_paise / PAISE_PER_INR

    @property
    def total_settled_inr(self) -> float:
        return self.total_settled_paise / PAISE_PER_INR

    @property
    def unused_permit_value_released_inr(self) -> float:
        return self.unused_permit_value_released_paise / PAISE_PER_INR

    @property
    def stranded_inr(self) -> float:
        return self.stranded_paise / PAISE_PER_INR

    @property
    def total_claimed_inr(self) -> float:
        return self.total_claimed_paise / PAISE_PER_INR

    @property
    def total_settled_inr(self) -> float:
        return self.total_settled_paise / PAISE_PER_INR

    @property
    def stranded_inr(self) -> float:
        return self.stranded_paise / PAISE_PER_INR


@dataclass
class AttackEventRecord:
    """Record of an offline transaction event, receiver acceptance, and adversary payoff."""
    experiment_name: str
    policy: str
    tx_uuid: str
    allowance_id: str
    permit_id: str
    payer_id: str
    payer_is_attacker: bool
    payer_role: str
    payee_id: str
    claim_type: str
    ingestion_sequence: int
    requested_paise: int
    offline_accepted: bool
    goods_released: bool
    goods_value_paise: int
    attack_costs_paise: int
    settlement_status: str
    paid_paise: int
    mule_credit_paise: int
    funded_c_paise: int
    funded_h_paise: int
    funded_f_paise: int
    attacker_id: str = "attacker_001"
    attacker_controls_payer: bool = False
    attacker_controls_payee: bool = False
    payer_is_victim: bool = False
    pos_validation_passed: bool = True
    centre_validation_passed: bool = True
    settlement_eligible: bool = True
    rejection_reason: str = ""
    goods_release_value_paise: int = 0
    recoverable_mule_credit_paise: int = 0
    payer_owned_debit_paise: int = 0
    issuer_expenditure_paise: int = 0
    attacker_gross_benefit_paise: int = 0
    attacker_net_profit_paise: int = 0


class TelemetryLogger:
    """Collects system-wide permit inventory, attack event telemetry, and blockchain audit anchors."""

    def __init__(self, adapter: Optional[BlockchainAdapter] = None) -> None:
        self.permit_records: List[PermitInventoryRecord] = []
        self.attack_records: List[AttackEventRecord] = []
        self.anchor_records: List[AuditAnchorRecord] = []
        self.adapter: BlockchainAdapter = adapter or SimulatedEVMAdapter()

    def record_settlement(
        self,
        experiment_name: str,
        allowance: Allowance,
        batch_result: SettlementBatchResult,
        payer_is_attacker: bool = True,
        attack_costs_paise: int = 0,
    ) -> None:
        """Process a settlement batch to update permit inventory and log attack events."""
        policy_name = batch_result.policy.value
        permit_map: Dict[str, Permit] = {p.permit_id: p for p in allowance.permits}

        # Track usage per permit in this batch
        claims_by_permit: Dict[str, List] = {p.permit_id: [] for p in allowance.permits}
        for cr in batch_result.claim_results:
            if cr.claim.permit_id in claims_by_permit:
                claims_by_permit[cr.claim.permit_id].append(cr)

        # 1. Update Permit Inventory
        for p in allowance.permits:
            crs = claims_by_permit.get(p.permit_id, [])
            claims_count = len(crs)
            conflicting_claims_count = max(0, claims_count - 1) if claims_count > 1 else 0
            total_claimed = sum(cr.requested_amount for cr in crs)
            total_settled = sum(cr.paid_amount for cr in crs)
            is_used = claims_count > 0
            is_double_spent = claims_count > 1
            unused_released = max(0, p.denomination - total_claimed) if total_claimed < p.denomination else 0
            stranded = max(0, p.denomination - total_settled) if total_settled < p.denomination else 0

            if not is_used:
                p_status = "UNUSED"
            elif is_double_spent:
                p_status = "DOUBLE_SPENT"
            elif total_settled == p.denomination:
                p_status = "CONSUMED_FULL"
            elif total_settled > 0:
                p_status = "CONSUMED_PARTIAL"
            else:
                p_status = "REJECTED_UNPAID"

            self.permit_records.append(
                PermitInventoryRecord(
                    allowance_id=allowance.allowance_id,
                    permit_id=p.permit_id,
                    payer_id=p.payer_id,
                    denomination_paise=p.denomination,
                    policy=policy_name,
                    claims_count=claims_count,
                    conflicting_claims_count=conflicting_claims_count,
                    total_claimed_paise=total_claimed,
                    settlement_payout_attributed_paise=total_settled,
                    total_settled_paise=total_settled,
                    is_used=is_used,
                    is_double_spent=is_double_spent,
                    unused_permit_value_released_paise=unused_released,
                    stranded_paise=stranded,
                    permit_status=p_status,
                )
            )

        # 2. Log Attack Events
        for cr in batch_result.claim_results:
            c = cr.claim
            pos_val = getattr(c, "pos_validation_passed", True)
            offline_acc = getattr(c, "offline_accepted", True)
            centre_val = cr.validation_passed
            settle_eligible = getattr(cr, "settlement_eligible", True)
            rej_reason = cr.rejection_reason or ""

            # Ownership & attribution
            attacker_id = getattr(c, "attacker_id", "attacker_001")
            ctrl_payer = getattr(c, "attacker_controls_payer", False)
            if not ctrl_payer and payer_is_attacker:
                ctrl_payer = True

            ctrl_payee = getattr(c, "attacker_controls_payee", False)
            if not ctrl_payee and c.claim_type in (ClaimType.MULE, ClaimType.ATTACKER_SELF):
                ctrl_payee = True

            payer_victim = getattr(c, "payer_is_victim", False)
            if not payer_victim and not payer_is_attacker:
                payer_victim = True

            # Goods released invariant: Unified POS offline outcome
            goods_released = is_claim_goods_acquired(c, centre_validation_passed=centre_val)
            goods_release_val = c.amount if goods_released else 0

            # Recoverable mule credit: settled payout to attacker-controlled payee
            mule_credit = cr.paid_amount if ctrl_payee else 0

            # Financial debits
            payer_debit = cr.funded_from_c + cr.funded_from_h
            issuer_exp = cr.funded_from_f
            costs = getattr(c, "attack_costs_paise", 0) or attack_costs_paise

            # Gross benefit = Goods acquired + Recoverable mule credit
            gross_benefit = goods_release_val + mule_credit

            # Net profit formulation preventing double counting
            if ctrl_payer:
                net_profit = gross_benefit - payer_debit - costs
            elif payer_victim:
                net_profit = gross_benefit - costs
            else:
                net_profit = mule_credit - costs

            payer_role = "ATTACKER_SELF" if ctrl_payer else ("VICTIM_CLONED" if payer_victim else "HONEST_PAYER")

            self.attack_records.append(
                AttackEventRecord(
                    experiment_name=experiment_name,
                    policy=policy_name,
                    tx_uuid=c.tx_uuid,
                    allowance_id=c.allowance_id,
                    permit_id=c.permit_id,
                    payer_id=c.payer_id,
                    payer_is_attacker=ctrl_payer,
                    payer_role=payer_role,
                    payee_id=c.payee_id,
                    claim_type=c.claim_type.value,
                    ingestion_sequence=c.ingestion_sequence,
                    requested_paise=c.amount,
                    offline_accepted=offline_acc,
                    goods_released=goods_released,
                    goods_value_paise=goods_release_val,
                    attack_costs_paise=costs,
                    settlement_status=cr.status.value,
                    paid_paise=cr.paid_amount,
                    mule_credit_paise=mule_credit,
                    funded_c_paise=cr.funded_from_c,
                    funded_h_paise=cr.funded_from_h,
                    funded_f_paise=cr.funded_from_f,
                    attacker_id=attacker_id,
                    attacker_controls_payer=ctrl_payer,
                    attacker_controls_payee=ctrl_payee,
                    payer_is_victim=payer_victim,
                    pos_validation_passed=pos_val,
                    centre_validation_passed=centre_val,
                    settlement_eligible=settle_eligible,
                    rejection_reason=rej_reason,
                    goods_release_value_paise=goods_release_val,
                    recoverable_mule_credit_paise=mule_credit,
                    payer_owned_debit_paise=payer_debit,
                    issuer_expenditure_paise=issuer_exp,
                    attacker_gross_benefit_paise=gross_benefit,
                    attacker_net_profit_paise=net_profit,
                )
            )

        # 3. Construct and Anchor Audit Merkle Tree
        claims = [cr.claim for cr in batch_result.claim_results]
        batch_id = f"batch_{experiment_name}_{policy_name}_{allowance.allowance_id}_{len(self.anchor_records) + 1}"
        tree, events = AuditSettlementPipeline.generate_batch_audit_trail(
            batch_id=batch_id,
            allowance=allowance,
            claims=claims,
            batch_result=batch_result,
        )

        try:
            receipt = self.adapter.anchor_root(
                batch_id,
                tree.root_hex,
                event_count=len(events),
                anchor_attempts=1,
            )
            self.anchor_records.append(
                AuditAnchorRecord(
                    experiment_name=experiment_name,
                    policy=policy_name,
                    batch_id=batch_id,
                    allowance_id=allowance.allowance_id,
                    event_count=len(events),
                    merkle_root=tree.root_hex,
                    tx_hash=receipt.tx_hash,
                    block_number=receipt.block_number,
                    gas_used=receipt.gas_used,
                    status="ANCHORED",
                    chain_id=receipt.chain_id,
                    contract_address=receipt.contract_address,
                    contract_version=receipt.contract_version,
                    transaction_hash=receipt.tx_hash,
                    block_timestamp=receipt.block_timestamp,
                    receipt_status=receipt.receipt_status,
                    confirmation_count=receipt.confirmation_count,
                    actual_gas_used=receipt.actual_gas_used,
                    anchor_attempts=receipt.anchor_attempts,
                    execution_environment=receipt.execution_environment,
                )
            )
        except Exception as e:
            self.anchor_records.append(
                AuditAnchorRecord(
                    experiment_name=experiment_name,
                    policy=policy_name,
                    batch_id=batch_id,
                    allowance_id=allowance.allowance_id,
                    event_count=len(events),
                    merkle_root=tree.root_hex,
                    tx_hash="",
                    block_number=0,
                    gas_used=0,
                    status=f"FAILED: {e}",
                    receipt_status="FAILED_UNANCHORED",
                    execution_environment="MOCK_SIMULATED_EVM",
                )
            )

    def export_permit_inventory_csv(self, file_path: str) -> None:
        """Export complete permit inventory to CSV."""
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        fieldnames = [
            "allowance_id",
            "permit_id",
            "payer_id",
            "policy",
            "denomination_paise",
            "denomination_inr",
            "claims_count",
            "conflicting_claims_count",
            "total_claimed_paise",
            "total_claimed_inr",
            "settlement_payout_attributed_paise",
            "settlement_payout_attributed_inr",
            "total_settled_paise",
            "total_settled_inr",
            "is_used",
            "is_double_spent",
            "unused_permit_value_released_paise",
            "unused_permit_value_released_inr",
            "stranded_paise",
            "stranded_inr",
            "permit_status",
        ]
        with open(file_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in self.permit_records:
                writer.writerow({
                    "allowance_id": r.allowance_id,
                    "permit_id": r.permit_id,
                    "payer_id": r.payer_id,
                    "policy": r.policy,
                    "denomination_paise": r.denomination_paise,
                    "denomination_inr": f"{r.denomination_inr:.2f}",
                    "claims_count": r.claims_count,
                    "conflicting_claims_count": r.conflicting_claims_count,
                    "total_claimed_paise": r.total_claimed_paise,
                    "total_claimed_inr": f"{r.total_claimed_inr:.2f}",
                    "settlement_payout_attributed_paise": r.settlement_payout_attributed_paise,
                    "settlement_payout_attributed_inr": f"{r.settlement_payout_attributed_inr:.2f}",
                    "total_settled_paise": r.total_settled_paise,
                    "total_settled_inr": f"{r.total_settled_inr:.2f}",
                    "is_used": r.is_used,
                    "is_double_spent": r.is_double_spent,
                    "unused_permit_value_released_paise": r.unused_permit_value_released_paise,
                    "unused_permit_value_released_inr": f"{r.unused_permit_value_released_inr:.2f}",
                    "stranded_paise": r.stranded_paise,
                    "stranded_inr": f"{r.stranded_inr:.2f}",
                    "permit_status": r.permit_status,
                })

    def export_attack_events_csv(self, file_path: str) -> None:
        """Export attack events, validation breakdown, and economic telemetry to CSV."""
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        fieldnames = [
            "experiment_name",
            "policy",
            "tx_uuid",
            "allowance_id",
            "permit_id",
            "payer_id",
            "attacker_id",
            "attacker_controls_payer",
            "attacker_controls_payee",
            "payer_is_victim",
            "payer_role",
            "payee_id",
            "claim_type",
            "ingestion_sequence",
            "pos_validation_passed",
            "offline_accepted",
            "goods_released",
            "centre_validation_passed",
            "settlement_eligible",
            "rejection_reason",
            "settlement_status",
            "requested_paise",
            "requested_inr",
            "goods_release_value_paise",
            "goods_release_value_inr",
            "paid_paise",
            "paid_inr",
            "mule_credit_paise",
            "mule_credit_inr",
            "recoverable_mule_credit_paise",
            "recoverable_mule_credit_inr",
            "funded_c_paise",
            "funded_h_paise",
            "funded_f_paise",
            "payer_owned_debit_paise",
            "issuer_expenditure_paise",
            "attack_costs_paise",
            "attack_costs_inr",
            "attacker_gross_benefit_paise",
            "attacker_net_profit_paise",
            "attacker_net_profit_inr",
        ]
        with open(file_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in self.attack_records:
                writer.writerow({
                    "experiment_name": r.experiment_name,
                    "policy": r.policy,
                    "tx_uuid": r.tx_uuid,
                    "allowance_id": r.allowance_id,
                    "permit_id": r.permit_id,
                    "payer_id": r.payer_id,
                    "attacker_id": r.attacker_id,
                    "attacker_controls_payer": r.attacker_controls_payer,
                    "attacker_controls_payee": r.attacker_controls_payee,
                    "payer_is_victim": r.payer_is_victim,
                    "payer_role": r.payer_role,
                    "payee_id": r.payee_id,
                    "claim_type": r.claim_type,
                    "ingestion_sequence": r.ingestion_sequence,
                    "pos_validation_passed": r.pos_validation_passed,
                    "offline_accepted": r.offline_accepted,
                    "goods_released": r.goods_released,
                    "centre_validation_passed": r.centre_validation_passed,
                    "settlement_eligible": r.settlement_eligible,
                    "rejection_reason": r.rejection_reason,
                    "settlement_status": r.settlement_status,
                    "requested_paise": r.requested_paise,
                    "requested_inr": f"{r.requested_paise / PAISE_PER_INR:.2f}",
                    "goods_release_value_paise": r.goods_release_value_paise,
                    "goods_release_value_inr": f"{r.goods_release_value_paise / PAISE_PER_INR:.2f}",
                    "paid_paise": r.paid_paise,
                    "paid_inr": f"{r.paid_paise / PAISE_PER_INR:.2f}",
                    "mule_credit_paise": r.recoverable_mule_credit_paise,
                    "mule_credit_inr": f"{r.recoverable_mule_credit_paise / PAISE_PER_INR:.2f}",
                    "recoverable_mule_credit_paise": r.recoverable_mule_credit_paise,
                    "recoverable_mule_credit_inr": f"{r.recoverable_mule_credit_paise / PAISE_PER_INR:.2f}",
                    "funded_c_paise": r.funded_c_paise,
                    "funded_h_paise": r.funded_h_paise,
                    "funded_f_paise": r.funded_f_paise,
                    "payer_owned_debit_paise": r.payer_owned_debit_paise,
                    "issuer_expenditure_paise": r.issuer_expenditure_paise,
                    "attack_costs_paise": r.attack_costs_paise,
                    "attack_costs_inr": f"{r.attack_costs_paise / PAISE_PER_INR:.2f}",
                    "attacker_gross_benefit_paise": r.attacker_gross_benefit_paise,
                    "attacker_net_profit_paise": r.attacker_net_profit_paise,
                    "attacker_net_profit_inr": f"{r.attacker_net_profit_paise / PAISE_PER_INR:.2f}",
                })

    def export_audit_anchors_csv(self, file_path: str) -> None:
        """Export blockchain audit anchor records to CSV."""
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        fieldnames = [
            "chain_id",
            "contract_address",
            "contract_version",
            "transaction_hash",
            "block_number",
            "block_timestamp",
            "receipt_status",
            "confirmation_count",
            "actual_gas_used",
            "batch_id",
            "merkle_root",
            "event_count",
            "anchor_attempts",
            "execution_environment",
            "experiment_name",
            "policy",
            "allowance_id",
            "status",
        ]
        with open(file_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in self.anchor_records:
                writer.writerow({
                    "chain_id": r.chain_id,
                    "contract_address": r.contract_address,
                    "contract_version": r.contract_version,
                    "transaction_hash": r.transaction_hash or r.tx_hash,
                    "block_number": r.block_number,
                    "block_timestamp": r.block_timestamp,
                    "receipt_status": r.receipt_status,
                    "confirmation_count": r.confirmation_count,
                    "actual_gas_used": r.actual_gas_used,
                    "batch_id": r.batch_id,
                    "merkle_root": r.merkle_root,
                    "event_count": r.event_count,
                    "anchor_attempts": r.anchor_attempts,
                    "execution_environment": r.execution_environment,
                    "experiment_name": r.experiment_name,
                    "policy": r.policy,
                    "allowance_id": r.allowance_id,
                    "status": r.status,
                })
