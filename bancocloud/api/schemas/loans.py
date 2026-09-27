from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field

class LoanApplicationRequest(BaseModel):
    account_ref: UUID
    amount: Decimal = Field(gt=0, le=50000, max_digits=18, decimal_places=2)
    term_months: int = Field(ge=6, le=60)
    monthly_income: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
