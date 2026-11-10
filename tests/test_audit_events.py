"""Unit tests for canonical serialization, domain-separated hashing, and audit events."""

import pytest
from offline_payment.audit.canonicalization import canonicalize, to_canonical_json
from offline_payment.audit.events import (
    AuditEvent,
    AuditEventType,
    AllowanceCreatedPayload,
    ClaimIngestedPayload,
    SettlementAllocatedPayload,
)
from offline_payment.audit.hashing import (
    domain_hash_leaf,
    domain_hash_node,
    sha256_bytes,
)


def test_canonical_json_deterministic_key_ordering():
    dict_a = {"z": 1, "a": 2, "m": {"b": 3, "a": 4}}
    dict_b = {"a": 2, "m": {"a": 4, "b": 3}, "z": 1}

    json_a = to_canonical_json(dict_a)
    json_b = to_canonical_json(dict_b)

    assert json_a == json_b
    assert json_a == '{"a":2,"m":{"a":4,"b":3},"z":1}'
    assert canonicalize(dict_a) == canonicalize(dict_b)


def test_canonical_json_forbids_floats():
    with pytest.raises(ValueError, match="Floating point numbers are forbidden"):
        to_canonical_json({"amount": 10.5})


def test_domain_separated_hashing_different_from_raw():
    raw_data = b"claim_tx_uuid_12345"
    raw_sha = sha256_bytes(raw_data)
    leaf_sha = domain_hash_leaf(raw_data)

    assert raw_sha != leaf_sha

    # Test internal node domain separation
    left = sha256_bytes(b"node_left")
    right = sha256_bytes(b"node_right")
    raw_concat_sha = sha256_bytes(left + right)
    node_sha = domain_hash_node(left, right)

    assert raw_concat_sha != node_sha


def test_domain_hash_node_validates_32_byte_inputs():
    with pytest.raises(ValueError, match="must be exactly 32 bytes"):
        domain_hash_node(b"short", b"short")


def test_audit_event_creation_and_hashing():
    payload = AllowanceCreatedPayload(
        allowance_id="alw_test_01",
        payer_id="payer_alice",
        allowance_amount_paise=50000,
        payer_hold_paise=50000,
        issuer_guarantee_paise=0,
        total_reserve_paise=100000,
        settlement_deadline=1700000000,
    )

    event = AuditEvent.create(
        event_type=AuditEventType.ALLOWANCE_CREATED,
        sequence_number=1,
        payload=payload,
        timestamp=1690000000,
        event_id="evt_fixed_id",
    )

    c_bytes = event.canonical_bytes()
    assert isinstance(c_bytes, bytes)
    assert b"alw_test_01" in c_bytes
    assert b"payer_alice" in c_bytes

    h_hex = event.leaf_hash_hex()
    assert len(h_hex) == 64
    assert h_hex == domain_hash_leaf(c_bytes).hex()


def test_audit_event_payload_types():
    claim_payload = ClaimIngestedPayload(
        tx_uuid="tx_uuid_101",
        allowance_id="alw_01",
        permit_id="pmt_01",
        payer_id="payer_alice",
        payee_id="merchant_bob",
        amount_paise=50000,
        ingestion_sequence=1,
        submission_time=1690000050,
        claim_type="HONEST_MERCHANT",
    )
    event = AuditEvent.create(
        event_type=AuditEventType.CLAIM_INGESTED,
        sequence_number=2,
        payload=claim_payload,
    )
    assert event.payload["tx_uuid"] == "tx_uuid_101"
    assert event.payload["amount_paise"] == 50000
