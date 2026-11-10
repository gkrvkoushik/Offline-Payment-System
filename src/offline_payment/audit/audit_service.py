"""Audit settlement pipeline converting settlement outcomes into anchored Merkle trees."""

from typing import Dict, List, Optional, Tuple
import uuid

from offline_payment.audit.events import (
    AuditEvent,
    AuditEventType,
    AllowanceCreatedPayload,
    PermitIssuedPayload,
    ClaimIngestedPayload,
    ValidationEvaluatedPayload,
    SettlementAllocatedPayload,
    BatchClosedPayload,
)
from offline_payment.audit.merkle_tree import MerkleTree
from offline_payment.audit.proofs import MerkleProof
from offline_payment.models.allowance import Allowance
from offline_payment.models.claim import Claim
from offline_payment.settlement.base import SettlementBatchResult


class AuditSettlementPipeline:
    """Pipelines settlement batches into canonical audit events and Merkle trees."""

    @staticmethod
    def generate_batch_audit_trail(
        batch_id: str,
        allowance: Allowance,
        claims: List[Claim],
        batch_result: SettlementBatchResult,
    ) -> Tuple[MerkleTree, List[AuditEvent]]:
        """Construct the canonical audit trail and Merkle tree for a settlement batch."""
        events: List[AuditEvent] = []
        seq = 1

        # 1. ALLOWANCE_CREATED event
        allowance_payload = AllowanceCreatedPayload(
            allowance_id=allowance.allowance_id,
            payer_id=allowance.payer_id,
            allowance_amount_paise=allowance.allowance_amount,
            payer_hold_paise=allowance.payer_hold,
            issuer_guarantee_paise=allowance.issuer_guarantee,
            total_reserve_paise=allowance.total_reserve,
            settlement_deadline=allowance.settlement_deadline,
        )
        events.append(
            AuditEvent.create(
                event_type=AuditEventType.ALLOWANCE_CREATED,
                sequence_number=seq,
                payload=allowance_payload,
                event_id=f"{batch_id}_evt_{seq:04d}",
            )
        )
        seq += 1

        # 2. PERMIT_ISSUED events
        for permit in allowance.permits:
            permit_payload = PermitIssuedPayload(
                permit_id=permit.permit_id,
                allowance_id=permit.allowance_id,
                payer_id=permit.payer_id,
                denomination_paise=permit.denomination,
                settlement_deadline=permit.settlement_deadline,
                issuer_signature=permit.issuer_signature,
            )
            events.append(
                AuditEvent.create(
                    event_type=AuditEventType.PERMIT_ISSUED,
                    sequence_number=seq,
                    payload=permit_payload,
                    event_id=f"{batch_id}_evt_{seq:04d}",
                )
            )
            seq += 1

        # 3. CLAIM_INGESTED events
        claim_map: Dict[str, Claim] = {}
        for claim in claims:
            claim_map[claim.tx_uuid] = claim
            claim_payload = ClaimIngestedPayload(
                tx_uuid=claim.tx_uuid,
                allowance_id=claim.allowance_id,
                permit_id=claim.permit_id,
                payer_id=claim.payer_id,
                payee_id=claim.payee_id,
                amount_paise=claim.amount,
                ingestion_sequence=claim.ingestion_sequence,
                submission_time=claim.submission_time,
                claim_type=claim.claim_type.value,
            )
            events.append(
                AuditEvent.create(
                    event_type=AuditEventType.CLAIM_INGESTED,
                    sequence_number=seq,
                    payload=claim_payload,
                    event_id=f"{batch_id}_evt_{seq:04d}",
                )
            )
            seq += 1

        # 4. VALIDATION_EVALUATED & SETTLEMENT_ALLOCATED events per claim result
        for cr in batch_result.claim_results:
            claim = cr.claim
            is_replay = bool(cr.rejection_reason and "Duplicate" in cr.rejection_reason)
            is_conflict = bool(cr.rejection_reason and "conflict" in cr.rejection_reason.lower())

            val_payload = ValidationEvaluatedPayload(
                tx_uuid=claim.tx_uuid,
                allowance_id=claim.allowance_id,
                permit_id=claim.permit_id,
                pos_validation_passed=claim.offline_accepted,
                centre_validation_passed=cr.validation_passed,
                is_replay=is_replay,
                is_conflict=is_conflict,
                rejection_reason=cr.rejection_reason,
            )
            events.append(
                AuditEvent.create(
                    event_type=AuditEventType.VALIDATION_EVALUATED,
                    sequence_number=seq,
                    payload=val_payload,
                    event_id=f"{batch_id}_evt_{seq:04d}",
                )
            )
            seq += 1

            settle_payload = SettlementAllocatedPayload(
                batch_id=batch_id,
                policy=batch_result.policy.value,
                tx_uuid=claim.tx_uuid,
                allowance_id=claim.allowance_id,
                permit_id=claim.permit_id,
                payee_id=claim.payee_id,
                requested_paise=cr.requested_amount,
                paid_paise=cr.paid_amount,
                funded_c_paise=cr.funded_from_c,
                funded_h_paise=cr.funded_from_h,
                funded_f_paise=cr.funded_from_f,
                status=cr.status.value,
            )
            events.append(
                AuditEvent.create(
                    event_type=AuditEventType.SETTLEMENT_ALLOCATED,
                    sequence_number=seq,
                    payload=settle_payload,
                    event_id=f"{batch_id}_evt_{seq:04d}",
                )
            )
            seq += 1

        # 5. BATCH_CLOSED event
        batch_closed_payload = BatchClosedPayload(
            batch_id=batch_id,
            policy=batch_result.policy.value,
            allowance_id=allowance.allowance_id,
            total_claims_count=batch_result.total_claims_count,
            total_eligible_count=batch_result.total_eligible_count,
            total_requested_paise=batch_result.total_requested_amount,
            total_paid_paise=batch_result.total_payout,
            remaining_reserve_paise=batch_result.remaining_reserve,
            event_count=len(events) + 1,
        )
        events.append(
            AuditEvent.create(
                event_type=AuditEventType.BATCH_CLOSED,
                sequence_number=seq,
                payload=batch_closed_payload,
                event_id=f"{batch_id}_evt_{seq:04d}",
            )
        )

        # Build Merkle Tree from canonical audit events
        merkle_tree = MerkleTree(events)
        return merkle_tree, events

    @staticmethod
    def get_claim_proof(
        tx_uuid: str,
        events: List[AuditEvent],
        merkle_tree: MerkleTree,
        event_type: AuditEventType = AuditEventType.SETTLEMENT_ALLOCATED,
    ) -> Optional[MerkleProof]:
        """Find the leaf index of a specific claim event and generate its Merkle inclusion proof."""
        for idx, evt in enumerate(events):
            if evt.event_type == event_type and evt.payload.get("tx_uuid") == tx_uuid:
                return merkle_tree.generate_proof(idx)
        return None
