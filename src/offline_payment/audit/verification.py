"""Independent audit verification service validating on-chain anchors and settlement proofs."""

from dataclasses import dataclass, field
from typing import List, Optional

from offline_payment.audit.events import AuditEvent, AuditEventType
from offline_payment.audit.merkle_tree import MerkleTree
from offline_payment.audit.proofs import MerkleProof, verify_merkle_proof
from offline_payment.blockchain.adapter import BlockchainAdapter
from offline_payment.models.allowance import Allowance


@dataclass
class AuditVerificationReport:
    """Report detailing independent verification of an anchored settlement batch."""
    batch_id: str
    is_valid: bool
    root_matched_on_chain: bool
    merkle_tree_verified: bool
    conservation_of_funds_valid: bool
    monotonic_sequence_valid: bool
    total_claims_verified: int
    total_paid_paise: int
    total_funded_paise: int
    errors: List[str] = field(default_factory=list)


class IndependentAuditVerifier:
    """External auditor service verifying settlement proofs without trusting the operator."""

    @staticmethod
    def verify_claim_inclusion_against_anchor(
        adapter: BlockchainAdapter,
        batch_id: str,
        proof: MerkleProof,
    ) -> bool:
        """Verify an individual claim's inclusion proof against the immutable on-chain root."""
        anchor = adapter.get_anchor(batch_id)
        if not anchor:
            return False

        clean_onchain_root = anchor.merkle_root.removeprefix("0x").lower()
        clean_proof_root = proof.root_hash.removeprefix("0x").lower()

        if clean_onchain_root != clean_proof_root:
            return False

        return verify_merkle_proof(proof)

    @staticmethod
    def verify_batch_audit_trail(
        adapter: BlockchainAdapter,
        batch_id: str,
        events: List[AuditEvent],
        allowance: Allowance,
    ) -> AuditVerificationReport:
        """Independently recompute and verify an entire settlement audit trail.

        Checks:
        1. On-chain anchor existence and root equivalence.
        2. Merkle tree reconstruction and root match.
        3. Strict monotonic sequence numbers (1, 2, 3, ...).
        4. Conservation of funds across funding tiers:
           - Sum(funded_c) <= allowance.allowance_amount (C)
           - Sum(funded_h) <= allowance.payer_hold (H)
           - Sum(funded_f) <= allowance.issuer_guarantee (F)
           - Sum(paid_paise) == Sum(funded_c + funded_h + funded_f) <= Total Reserve S
        5. Claim-level non-overpayment (paid_paise <= requested_paise, paid_paise >= 0).
        """
        errors: List[str] = []

        # 1. On-chain check
        anchor = adapter.get_anchor(batch_id)
        if not anchor:
            return AuditVerificationReport(
                batch_id=batch_id,
                is_valid=False,
                root_matched_on_chain=False,
                merkle_tree_verified=False,
                conservation_of_funds_valid=False,
                monotonic_sequence_valid=False,
                total_claims_verified=0,
                total_paid_paise=0,
                total_funded_paise=0,
                errors=[f"Anchor for batch {batch_id} not found on blockchain"],
            )

        # 2. Recompute Merkle root
        recomputed_tree = MerkleTree(events)
        recomputed_root = recomputed_tree.root_hex.lower()
        onchain_root = anchor.merkle_root.removeprefix("0x").lower()

        root_matched = (recomputed_root == onchain_root)
        if not root_matched:
            errors.append(
                f"Recomputed root ({recomputed_root}) does not match on-chain root ({onchain_root})"
            )

        # 3. Monotonic sequence check
        monotonic_valid = True
        for i, evt in enumerate(events):
            expected_seq = i + 1
            if evt.sequence_number != expected_seq:
                monotonic_valid = False
                errors.append(
                    f"Non-monotonic sequence: event index {i} has seq {evt.sequence_number}, expected {expected_seq}"
                )
                break

        # 4. Conservation of funds check
        total_funded_c = 0
        total_funded_h = 0
        total_funded_f = 0
        total_paid = 0
        settlement_events_count = 0

        for evt in events:
            if evt.event_type == AuditEventType.SETTLEMENT_ALLOCATED:
                settlement_events_count += 1
                p = evt.payload
                req = p["requested_paise"]
                paid = p["paid_paise"]
                fc = p["funded_c_paise"]
                fh = p["funded_h_paise"]
                ff = p["funded_f_paise"]

                if paid < 0:
                    errors.append(f"Negative payout for claim {p['tx_uuid']}: {paid}")
                if paid > req:
                    errors.append(f"Payout {paid} exceeds requested {req} for claim {p['tx_uuid']}")
                if fc + fh + ff != paid:
                    errors.append(
                        f"Funding tiers ({fc} + {fh} + {ff} = {fc+fh+ff}) != paid ({paid}) for claim {p['tx_uuid']}"
                    )

                total_funded_c += fc
                total_funded_h += fh
                total_funded_f += ff
                total_paid += paid

        conservation_valid = True
        if total_funded_c > allowance.allowance_amount:
            conservation_valid = False
            errors.append(
                f"Total C funded ({total_funded_c}) exceeds allowance C ({allowance.allowance_amount})"
            )
        if total_funded_h > allowance.payer_hold:
            conservation_valid = False
            errors.append(
                f"Total H funded ({total_funded_h}) exceeds payer hold H ({allowance.payer_hold})"
            )
        if total_funded_f > allowance.issuer_guarantee:
            conservation_valid = False
            errors.append(
                f"Total F funded ({total_funded_f}) exceeds issuer guarantee F ({allowance.issuer_guarantee})"
            )
        if total_paid > allowance.total_reserve:
            conservation_valid = False
            errors.append(
                f"Total paid ({total_paid}) exceeds total reserve S ({allowance.total_reserve})"
            )

        is_valid = root_matched and monotonic_valid and conservation_valid and len(errors) == 0

        return AuditVerificationReport(
            batch_id=batch_id,
            is_valid=is_valid,
            root_matched_on_chain=root_matched,
            merkle_tree_verified=root_matched,
            conservation_of_funds_valid=conservation_valid,
            monotonic_sequence_valid=monotonic_valid,
            total_claims_verified=settlement_events_count,
            total_paid_paise=total_paid,
            total_funded_paise=total_funded_c + total_funded_h + total_funded_f,
            errors=errors,
        )
