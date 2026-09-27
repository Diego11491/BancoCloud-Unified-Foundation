from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

DEFAULT_ANNUAL_RATE = Decimal("0.1899")
MAX_DTI = Decimal("0.35")


class LoanError(ValueError):
    pass


def calculate_monthly_payment(amount: Decimal, term_months: int, annual_rate: Decimal = DEFAULT_ANNUAL_RATE) -> Decimal:
    if amount <= 0:
        raise LoanError("Amount must be greater than zero")
    if term_months <= 0:
        raise LoanError("Term must be positive")
    if annual_rate <= 0:
        raise LoanError("Annual rate must be positive")
    monthly_rate = annual_rate / Decimal(12)
    factor = (Decimal(1) + monthly_rate) ** (-term_months)
    payment = amount * monthly_rate / (Decimal(1) - factor)
    return payment.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def evaluate_dti(amount: Decimal, term_months: int, monthly_income: Decimal, annual_rate: Decimal = DEFAULT_ANNUAL_RATE) -> tuple[bool, Decimal, Decimal]:
    if monthly_income <= 0:
        raise LoanError("Monthly income must be greater than zero")
    payment = calculate_monthly_payment(amount, term_months, annual_rate)
    dti = payment / monthly_income
    return dti <= MAX_DTI, payment, dti


@dataclass(frozen=True, slots=True)
class Loan:
    loan_ref: UUID
    customer_ref: UUID
    account_ref: UUID
    principal: Decimal
    annual_rate: Decimal
    term_months: int
    monthly_payment: Decimal
    outstanding_balance: Decimal
    days_past_due: int
    status: str