from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field

class CardPurchaseRequest(BaseModel):
    card_ref: UUID
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    currency: str = Field(default="PEN", min_length=3, max_length=3)
