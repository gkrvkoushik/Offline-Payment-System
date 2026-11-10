"""Claim validation and replay protection module."""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple, List
from offline_payment.models.claim import Claim
from offline_payment.models.allowance import Allowance
from offline_payment.models.permit import Permit


@dataclass
class ValidationResult:
    """Result of validating a claim before settlement."""
    claim: Claim
    is_valid: bool
    is_duplicate_replay: bool = False
    error_message: Optional[str] = None


class ClaimValidator:
    """Validates claims cryptographically and structurally, and tracks UUID replays.

    Important rules:
    - Reject claims with invalid signatures, non-positive amount, or amount > denomination.
    - Reject claims referencing non-existent allowances or permits.
    - Exact replay of the same transaction (identical UUID and content) is deduplicated.
    - Conflicting payload with existing UUID is rejected as a conflict.
    - Two DIFFERENT transaction UUIDs referencing the SAME permit are both cryptographically
      valid at this validation layer; double-spending conflicts are resolved by settlement policies.
    """

    def __init__(self, allowance: Allowance) -> None:
        self.allowance = allowance
        self.permits_by_id: Dict[str, Permit] = {p.permit_id: p for p in allowance.permits}
        # Tracks seen tx_uuid -> tuple of transaction contents for collision/replay detection
        self._seen_txs: Dict[str, Tuple[str, str, str, str, int]] = {}

    def _extract_payload_signature(self, claim: Claim) -> Tuple[str, str, str, str, int]:
        """Core transaction contents that define transaction identity."""
        return (
            claim.allowance_id,
            claim.permit_id,
            claim.payer_id,
            claim.payee_id,
            claim.amount,
        )

    def validate_claim(self, claim: Claim) -> ValidationResult:
        """Validate a single claim."""
        # 1. Structural / Non-positive amount
        if claim.amount <= 0:
            return ValidationResult(
                claim=claim,
                is_valid=False,
                error_message=f"Non-positive claim amount: {claim.amount}",
            )

        # 2. Allowance reference verification
        if claim.allowance_id != self.allowance.allowance_id:
            return ValidationResult(
                claim=claim,
                is_valid=False,
                error_message=f"Allowance ID mismatch: claim refers to {claim.allowance_id}, expected {self.allowance.allowance_id}",
            )

        # 3. Permit reference verification
        permit = self.permits_by_id.get(claim.permit_id)
        if permit is None:
            return ValidationResult(
                claim=claim,
                is_valid=False,
                error_message=f"Referenced permit {claim.permit_id} not found in allowance",
            )

        if permit.allowance_id != claim.allowance_id:
            return ValidationResult(
                claim=claim,
                is_valid=False,
                error_message=f"Permit {permit.permit_id} belongs to allowance {permit.allowance_id}, not {claim.allowance_id}",
            )

        if claim.payer_id != permit.payer_id:
            return ValidationResult(
                claim=claim,
                is_valid=False,
                error_message=f"Claim payer_id {claim.payer_id} does not match permit payer_id {permit.payer_id}",
            )

        # 4. Amount versus permit denomination
        if claim.amount > permit.denomination:
            return ValidationResult(
                claim=claim,
                is_valid=False,
                error_message=f"Claim amount {claim.amount} exceeds permit denomination {permit.denomination}",
            )

        # 5. Cryptographic signature checks
        if not claim.issuer_signature_valid:
            return ValidationResult(
                claim=claim,
                is_valid=False,
                error_message="Invalid issuer signature",
            )

        if not claim.payer_signature_valid:
            return ValidationResult(
                claim=claim,
                is_valid=False,
                error_message="Invalid payer signature",
            )

        if not claim.payee_signature_valid:
            return ValidationResult(
                claim=claim,
                is_valid=False,
                error_message="Invalid payee receipt signature",
            )

        # 6. Replay & UUID Collision checks
        payload = self._extract_payload_signature(claim)
        if claim.tx_uuid in self._seen_txs:
            existing_payload = self._seen_txs[claim.tx_uuid]
            if existing_payload == payload:
                # Exact replay -> deduplicate
                return ValidationResult(
                    claim=claim,
                    is_valid=False,
                    is_duplicate_replay=True,
                    error_message=f"Exact replay of transaction UUID {claim.tx_uuid} deduplicated",
                )
            else:
                # Same UUID with conflicting transaction contents -> reject conflict
                return ValidationResult(
                    claim=claim,
                    is_valid=False,
                    is_duplicate_replay=False,
                    error_message=f"Conflicting payload with existing transaction UUID {claim.tx_uuid}",
                )

        self._seen_txs[claim.tx_uuid] = payload
        return ValidationResult(claim=claim, is_valid=True)

    def validate_batch(self, claims: List[Claim]) -> Tuple[List[Claim], List[ValidationResult]]:
        """Validate a batch of claims preserving ingestion order.

        Returns:
            (eligible_claims, all_validation_results)
        """
        eligible: List[Claim] = []
        all_results: List[ValidationResult] = []

        # Sort by ingestion sequence to ensure deterministic validation order
        sorted_claims = sorted(claims, key=lambda c: c.ingestion_sequence)

        for claim in sorted_claims:
            res = self.validate_claim(claim)
            all_results.append(res)
            if res.is_valid:
                eligible.append(claim)

        return eligible, all_results
