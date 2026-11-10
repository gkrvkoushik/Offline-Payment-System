"""Account domain model representing user/payer ledger accounts."""

from dataclasses import dataclass
from offline_payment.config import AccountStatus


@dataclass
class Account:
    """Ledger account.

    All balances are denominated strictly in integer paise.
    Invariant: available_balance + locked_balance + held_balance = total_balance
    """
    account_id: str
    available_balance: int  # in paise
    locked_balance: int = 0  # in paise (e.g. allowance commitment C)
    held_balance: int = 0  # in paise (e.g. payer hold H)
    account_status: AccountStatus = AccountStatus.ACTIVE

    def __post_init__(self) -> None:
        if not isinstance(self.available_balance, int) or self.available_balance < 0:
            raise ValueError(f"available_balance must be non-negative integer paise, got {self.available_balance}")
        if not isinstance(self.locked_balance, int) or self.locked_balance < 0:
            raise ValueError(f"locked_balance must be non-negative integer paise, got {self.locked_balance}")
        if not isinstance(self.held_balance, int) or self.held_balance < 0:
            raise ValueError(f"held_balance must be non-negative integer paise, got {self.held_balance}")

    @property
    def total_balance(self) -> int:
        """Total balance in paise."""
        return self.available_balance + self.locked_balance + self.held_balance

    def lock_funds(self, amount: int) -> None:
        """Lock available funds for allowance commitment C."""
        if amount <= 0:
            raise ValueError("Amount to lock must be positive")
        if self.available_balance < amount:
            raise ValueError(
                f"Insufficient available balance ({self.available_balance}) to lock {amount}"
            )
        self.available_balance -= amount
        self.locked_balance += amount

    def hold_funds(self, amount: int) -> None:
        """Place hold on available funds for settlement guarantee H."""
        if amount <= 0:
            raise ValueError("Amount to hold must be positive")
        if self.available_balance < amount:
            raise ValueError(
                f"Insufficient available balance ({self.available_balance}) to hold {amount}"
            )
        self.available_balance -= amount
        self.held_balance += amount

    def settle_locked(self, amount: int) -> None:
        """Deduct settled funds from locked balance."""
        if amount < 0:
            raise ValueError("Settled amount cannot be negative")
        if self.locked_balance < amount:
            raise ValueError(
                f"Settled amount {amount} exceeds locked balance {self.locked_balance}"
            )
        self.locked_balance -= amount

    def settle_held(self, amount: int) -> None:
        """Deduct settled funds from held balance."""
        if amount < 0:
            raise ValueError("Settled amount cannot be negative")
        if self.held_balance < amount:
            raise ValueError(
                f"Settled amount {amount} exceeds held balance {self.held_balance}"
            )
        self.held_balance -= amount

    def release_unspent_hold(self) -> int:
        """Release any remaining held balance back to available balance."""
        released = self.held_balance
        self.available_balance += released
        self.held_balance = 0
        return released

    def release_unspent_lock(self) -> int:
        """Release any remaining locked balance back to available balance."""
        released = self.locked_balance
        self.available_balance += released
        self.locked_balance = 0
        return released
