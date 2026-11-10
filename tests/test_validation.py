"""Unit tests for claim validation and replay handling."""

import pytest
from offline_payment.config import ClaimType
from offline_payment.models.allowance import Allowance
from offline_payment.models.permit import Permit
from offline_payment.models.claim import Claim
from offline_payment.validation.claim_validator import ClaimValidator


@pytest.fixture
def sample_allowance():
    permit = Permit(
        permit_id="p_1",
        allowance_id="alw_1",
        payer_id="payer_1",
        payer_public_key="pubkey_1",
        denomination=50000,  # ₹500
        settlement_deadline=1000,
        issuer_signature="sig_issuer",
    )
    return Allowance(
        allowance_id="alw_1",
        payer_id="payer_1",
        allowance_amount=50000,
        payer_hold=50000,
        issuer_guarantee=0,
        settlement_deadline=1000,
        permits=[permit],
    )


def test_valid_claim(sample_allowance):
    validator = ClaimValidator(sample_allowance)
    claim = Claim(
        tx_uuid="tx-100",
        allowance_id="alw_1",
        permit_id="p_1",
        payer_id="payer_1",
        payee_id="merchant_a",
        amount=50000,
        ingestion_sequence=1,
        submission_time=10,
    )
    res = validator.validate_claim(claim)
    assert res.is_valid is True
    assert res.error_message is None


def test_invalid_signatures(sample_allowance):
    validator = ClaimValidator(sample_allowance)

    # Invalid issuer signature
    c1 = Claim(
        tx_uuid="tx-1",
        allowance_id="alw_1",
        permit_id="p_1",
        payer_id="payer_1",
        payee_id="m1",
        amount=50000,
        ingestion_sequence=1,
        submission_time=10,
        issuer_signature_valid=False,
    )
    assert validator.validate_claim(c1).is_valid is False
    assert "issuer signature" in validator.validate_claim(c1).error_message.lower()

    # Invalid payer signature
    c2 = Claim(
        tx_uuid="tx-2",
        allowance_id="alw_1",
        permit_id="p_1",
        payer_id="payer_1",
        payee_id="m1",
        amount=50000,
        ingestion_sequence=2,
        submission_time=11,
        payer_signature_valid=False,
    )
    assert validator.validate_claim(c2).is_valid is False
    assert "payer signature" in validator.validate_claim(c2).error_message.lower()

    # Invalid payee signature
    c3 = Claim(
        tx_uuid="tx-3",
        allowance_id="alw_1",
        permit_id="p_1",
        payer_id="payer_1",
        payee_id="m1",
        amount=50000,
        ingestion_sequence=3,
        submission_time=12,
        payee_signature_valid=False,
    )
    assert validator.validate_claim(c3).is_valid is False
    assert "payee receipt signature" in validator.validate_claim(c3).error_message.lower()


def test_amount_exceeding_denomination(sample_allowance):
    validator = ClaimValidator(sample_allowance)
    claim = Claim(
        tx_uuid="tx-4",
        allowance_id="alw_1",
        permit_id="p_1",
        payer_id="payer_1",
        payee_id="m1",
        amount=60000,  # exceeds 50000
        ingestion_sequence=1,
        submission_time=10,
    )
    res = validator.validate_claim(claim)
    assert res.is_valid is False
    assert "exceeds permit denomination" in res.error_message


def test_invalid_allowance_or_permit_reference(sample_allowance):
    validator = ClaimValidator(sample_allowance)

    # Wrong allowance ID
    c1 = Claim(
        tx_uuid="tx-5",
        allowance_id="alw_OTHER",
        permit_id="p_1",
        payer_id="payer_1",
        payee_id="m1",
        amount=50000,
        ingestion_sequence=1,
        submission_time=10,
    )
    assert validator.validate_claim(c1).is_valid is False
    assert "mismatch" in validator.validate_claim(c1).error_message.lower()

    # Non-existent permit ID
    c2 = Claim(
        tx_uuid="tx-6",
        allowance_id="alw_1",
        permit_id="p_NONEXISTENT",
        payer_id="payer_1",
        payee_id="m1",
        amount=50000,
        ingestion_sequence=2,
        submission_time=11,
    )
    assert validator.validate_claim(c2).is_valid is False
    assert "not found" in validator.validate_claim(c2).error_message.lower()


def test_replay_and_conflict_handling(sample_allowance):
    validator = ClaimValidator(sample_allowance)

    claim_original = Claim(
        tx_uuid="tx-duplicate",
        allowance_id="alw_1",
        permit_id="p_1",
        payer_id="payer_1",
        payee_id="m1",
        amount=50000,
        ingestion_sequence=1,
        submission_time=10,
    )
    res1 = validator.validate_claim(claim_original)
    assert res1.is_valid is True

    # Exact replay of same UUID and identical payload
    claim_replay = Claim(
        tx_uuid="tx-duplicate",
        allowance_id="alw_1",
        permit_id="p_1",
        payer_id="payer_1",
        payee_id="m1",
        amount=50000,
        ingestion_sequence=2,
        submission_time=15,
    )
    res2 = validator.validate_claim(claim_replay)
    assert res2.is_valid is False
    assert res2.is_duplicate_replay is True
    assert "deduplicated" in res2.error_message

    # Same UUID with different transaction payload -> conflict!
    claim_conflict = Claim(
        tx_uuid="tx-duplicate",
        allowance_id="alw_1",
        permit_id="p_1",
        payer_id="payer_1",
        payee_id="m2_attacker",  # Changed payee
        amount=50000,
        ingestion_sequence=3,
        submission_time=20,
    )
    res3 = validator.validate_claim(claim_conflict)
    assert res3.is_valid is False
    assert res3.is_duplicate_replay is False
    assert "Conflicting payload" in res3.error_message


def test_two_different_uuids_same_permit_both_pass_validation(sample_allowance):
    validator = ClaimValidator(sample_allowance)

    claim1 = Claim(
        tx_uuid="tx-uuid-1",
        allowance_id="alw_1",
        permit_id="p_1",
        payer_id="payer_1",
        payee_id="m1",
        amount=50000,
        ingestion_sequence=1,
        submission_time=10,
    )
    claim2 = Claim(
        tx_uuid="tx-uuid-2",
        allowance_id="alw_1",
        permit_id="p_1",
        payer_id="payer_1",
        payee_id="m2",
        amount=50000,
        ingestion_sequence=2,
        submission_time=11,
    )
    assert validator.validate_claim(claim1).is_valid is True
    assert validator.validate_claim(claim2).is_valid is True
