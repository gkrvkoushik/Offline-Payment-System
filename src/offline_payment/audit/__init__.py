"""Audit event definitions, canonicalization, and Merkle tree audit anchoring."""

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
from offline_payment.audit.canonicalization import canonicalize, to_canonical_json
from offline_payment.audit.hashing import (
    domain_hash_leaf,
    domain_hash_node,
    sha256_hex,
)
from offline_payment.audit.merkle_tree import MerkleTree
from offline_payment.audit.proofs import MerkleProof, verify_merkle_proof
from offline_payment.audit.audit_service import AuditSettlementPipeline
from offline_payment.audit.verification import (
    IndependentAuditVerifier,
    AuditVerificationReport,
)

__all__ = [
    "AuditEvent",
    "AuditEventType",
    "AllowanceCreatedPayload",
    "PermitIssuedPayload",
    "ClaimIngestedPayload",
    "ValidationEvaluatedPayload",
    "SettlementAllocatedPayload",
    "BatchClosedPayload",
    "canonicalize",
    "to_canonical_json",
    "domain_hash_leaf",
    "domain_hash_node",
    "sha256_hex",
    "MerkleTree",
    "MerkleProof",
    "verify_merkle_proof",
    "AuditSettlementPipeline",
    "IndependentAuditVerifier",
    "AuditVerificationReport",
]
