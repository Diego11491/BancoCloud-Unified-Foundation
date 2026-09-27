from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID


class CardError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Card:
    card_ref: UUID
    account_ref: UUID
    customer_ref: UUID
    card_type: str
    last_four: str
    credit_limit: Decimal | None
    used_balance: Decimal
    status: str

    @property
    def available_credit(self) -> Decimal | None:
        if self.credit_limit is None:
            return None
        return self.credit_limit - self.used_balance

    def validate_credit_purchase(self, amount: Decimal) -> Decimal:
        if amount <= 0:
            raise CardError("Amount must be greater than zero")
        if self.status != "ACTIVE":
            raise CardError(f"Card is not active (status: {self.status})")
        if self.card_type != "CREDIT":
            raise CardError("Card must be CREDIT type")
        if self.credit_limit is None:
            raise CardError("Card has no credit limit assigned")
        new_used = self.used_balance + amount
        if new_used > self.credit_limit:
            raise CardError(f"Credit limit exceeded; available {self.credit_limit - self.used_balance}")
        return new_used