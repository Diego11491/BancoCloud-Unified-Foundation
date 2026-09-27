from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Account:
    account_ref: UUID
    customer_ref: UUID
    balance: Decimal
    status: str = "ACTIVE"
