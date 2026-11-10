"""Canonical audit event models for the offline payment settlement lifecycle."""

from dataclasses import asdict, dataclass, field
from enum import Enum
import time
from typing import Any, Dict, Optional, Union
import uuid

from offline_payment.audit.canonicalization import canonicalize
from offline_payment.audit.hashing import domain_hash_leaf, domain_hash_leaf_hex


class AuditEventType(str, Enum):
    """Types of canonical events recorded in the audit trail."""
    ALLOWANCE_CREATED = "ALLOWANCE_CREATED"
    COLLATERAL_RESERVED = "COLLATERAL_RESERVED"
    PERMIT_ISSUED = "PERMIT_ISSUED"
    CLAIM_INGESTED = "CLAIM_INGESTED"
    VALIDATION_EVALUATED = "VALIDATION_EVALUATED"
    SETTLEMENT_ALLOCATED = "SETTLEMENT_ALLOCATED"
    BATCH_CLOSED = "BATCH_CLOSED"


@dataclass
class AllowanceCreatedPayload:
    allowance_id: str
    payer_id: str
    allowance_amount_paise: int
    payer_hold_paise: int
    issuer_guarantee_paise: int
    total_reserve_paise: int
    settlement_deadline: int


@dataclass
class PermitIssuedPayload:
    permit_id: str
    allowance_id: str
    payer_id: str
    denomination_paise: int
    settlement_deadline: int
    issuer_signature: str


@dataclass
class ClaimIngestedPayload:
    tx_uuid: str
    allowance_id: str
    permit_id: str
    payer_id: str
    payee_id: str
    amount_paise: int
    ingestion_sequence: int
    submission_time: int
    claim_type: str


@dataclass
class ValidationEvaluatedPayload:
    tx_uuid: str
    allowance_id: str
    permit_id: str
    pos_validation_passed: bool
    centre_validation_passed: bool
    is_replay: bool
    is_conflict: bool
    rejection_reason: Optional[str] = None


@dataclass
class SettlementAllocatedPayload:
    batch_id: str
    policy: str
    tx_uuid: str
    allowance_id: str
    permit_id: str
    payee_id: str
    requested_paise: int
    paid_paise: int
    funded_c_paise: int
    funded_h_paise: int
    funded_f_paise: int
    status: str


@dataclass
class BatchClosedPayload:
    batch_id: str
    policy: str
    allowance_id: str
    total_claims_count: int
    total_eligible_count: int
    total_requested_paise: int
    total_paid_paise: int
    remaining_reserve_paise: int
    event_count: int


PayloadType = Union[
    AllowanceCreatedPayload,
    PermitIssuedPayload,
    ClaimIngestedPayload,
    ValidationEvaluatedPayload,
    SettlementAllocatedPayload,
    BatchClosedPayload,
    Dict[str, Any],
]


@dataclass
class AuditEvent:
    """Canonical audit record.

    guarantees:
    - Immutable event identifier and monotonic sequence number.
    - Deterministic canonical serialization via RFC 8785.
    - Domain-separated leaf hashing (0x00 prefix).
    """
    event_type: AuditEventType
    sequence_number: int
    payload: Dict[str, Any]
    timestamp: int = field(default_factory=lambda: int(time.time()))
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    @classmethod
    def create(
        cls,
        event_type: AuditEventType,
        sequence_number: int,
        payload: PayloadType,
        timestamp: Optional[int] = None,
        event_id: Optional[str] = None,
    ) -> "AuditEvent":
        """Factory constructor accepting either typed dataclass payloads or raw dicts."""
        if hasattr(payload, "__dataclass_fields__"):
            raw_payload = asdict(payload)
        elif isinstance(payload, dict):
            raw_payload = dict(payload)
        else:
            raise TypeError(f"Payload must be a dataclass or dict, got {type(payload)}")

        kwargs: Dict[str, Any] = {
            "event_type": event_type,
            "sequence_number": sequence_number,
            "payload": raw_payload,
        }
        if timestamp is not None:
            kwargs["timestamp"] = timestamp
        if event_id is not None:
            kwargs["event_id"] = event_id
        return cls(**kwargs)

    def to_canonical_dict(self) -> Dict[str, Any]:
        """Convert event into a clean dictionary with predictable keys."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value if isinstance(self.event_type, Enum) else str(self.event_type),
            "payload": self.payload,
            "sequence_number": self.sequence_number,
            "timestamp": self.timestamp,
        }

    def canonical_bytes(self) -> bytes:
        """Produce deterministic canonical UTF-8 bytes."""
        return canonicalize(self.to_canonical_dict())

    def leaf_hash(self) -> bytes:
        """Domain-separated leaf hash: SHA-256(0x00 || canonical_bytes)."""
        return domain_hash_leaf(self.canonical_bytes())

    def leaf_hash_hex(self) -> str:
        """Domain-separated leaf hash as a 64-char hex string."""
        return domain_hash_leaf_hex(self.canonical_bytes())
