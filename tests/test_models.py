"""Unit tests for core domain models."""

import pytest
from offline_payment.config import AccountStatus, AllowanceStatus, PermitStatus, ClaimType
from offline_payment.models.account import Account
from offline_payment.models.allowance import Allowance
from offline_payment.models.permit import Permit
from offline_payment.models.claim import Claim


def test_account_creation_and_invariant():
    acc = Account(
        account_id="acc_1",
        available_balance=100000,  # ₹1000.00
        locked_balance=0,
        held_balance=0,
    )
    assert acc.total_balance == 100000
    assert acc.account_status == AccountStatus.ACTIVE

    acc.lock_funds(50000)
    assert acc.available_balance == 50000
    assert acc.locked_balance == 50000
    assert acc.held_balance == 0
    assert acc.total_balance == 100000  # Invariant holds

    acc.hold_funds(30000)
    assert acc.available_balance == 20000
    assert acc.locked_balance == 50000
    assert acc.held_balance == 30000
    assert acc.total_balance == 100000  # Invariant holds


def test_account_settlement_and_release():
    acc = Account(
        account_id="acc_1",
        available_balance=20000,
        locked_balance=50000,
        held_balance=30000,
    )
    # Settle partial locked
    acc.settle_locked(40000)
    assert acc.locked_balance == 10000
    assert acc.total_balance == 60000

    # Settle partial held
    acc.settle_held(15000)
    assert acc.held_balance == 15000
    assert acc.total_balance == 45000

    # Release remaining hold and lock
    released_hold = acc.release_unspent_hold()
    assert released_hold == 15000
    assert acc.held_balance == 0
    assert acc.available_balance == 35000

    released_lock = acc.release_unspent_lock()
    assert released_lock == 10000
    assert acc.locked_balance == 0
    assert acc.available_balance == 45000
    assert acc.total_balance == 45000


def test_account_validation_errors():
    with pytest.raises(ValueError):
        Account(account_id="acc_err", available_balance=-10)

    acc = Account(account_id="acc_1", available_balance=10000)
    with pytest.raises(ValueError, match="Insufficient available balance"):
        acc.lock_funds(20000)

    with pytest.raises(ValueError, match="exceeds locked balance"):
        acc.settle_locked(5000)


def test_permit_creation():
    p = Permit(
        permit_id="p_1",
        allowance_id="alw_1",
        payer_id="payer_1",
        payer_public_key="pubkey_123",
        denomination=50000,
        settlement_deadline=1700000000,
        issuer_signature="sig_issuer",
    )
    assert p.denomination == 50000
    assert p.status == PermitStatus.ACTIVE

    with pytest.raises(ValueError, match="positive integer"):
        Permit(
            permit_id="p_err",
            allowance_id="alw_1",
            payer_id="payer_1",
            payer_public_key="pubkey_123",
            denomination=0,
            settlement_deadline=1700000000,
            issuer_signature="sig",
        )


def test_allowance_funding_waterfall_totals():
    allowance = Allowance(
        allowance_id="alw_1",
        payer_id="payer_1",
        allowance_amount=50000,  # C = ₹500
        payer_hold=50000,        # H = ₹500
        issuer_guarantee=0,      # F = ₹0
        settlement_deadline=1700000000,
    )
    assert allowance.total_reserve == 100000  # S = C + H + F = 100000
    assert allowance.total_payer_backing == 100000  # C + H


def test_claim_crypto_validity_and_ground_truth():
    claim = Claim(
        tx_uuid="tx-1",
        allowance_id="alw_1",
        permit_id="p_1",
        payer_id="payer_1",
        payee_id="merchant_1",
        amount=50000,
        ingestion_sequence=1,
        submission_time=100,
        payer_signature_valid=True,
        payee_signature_valid=True,
        issuer_signature_valid=True,
        claim_type=ClaimType.MULE,  # Ground truth mule
    )
    # Ground truth mule does not impair cryptographic validity!
    assert claim.is_cryptographically_valid is True

    claim_invalid = Claim(
        tx_uuid="tx-2",
        allowance_id="alw_1",
        permit_id="p_1",
        payer_id="payer_1",
        payee_id="merchant_2",
        amount=50000,
        ingestion_sequence=2,
        submission_time=101,
        payer_signature_valid=False,
    )
    assert claim_invalid.is_cryptographically_valid is False
