from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field

class TransferRequest(BaseModel):
    source_account: UUID
    destination_account: UUID
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    device_ref: str | None = None
    beneficiary_ref: str | None = None
