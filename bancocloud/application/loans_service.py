from decimal import Decimal
from uuid import UUID
from bancocloud.domain.loans import DEFAULT_ANNUAL_RATE, MAX_DTI, evaluate_dti
from bancocloud.repositories.loans import LoanRepository


class LoansService:
    def __init__(self, repository: LoanRepository): self.repository = repository

    def apply(self, account_ref: UUID, amount: Decimal, term_months: int, monthly_income: Decimal) -> dict:
        approved, payment, dti = evaluate_dti(amount, term_months, monthly_income, DEFAULT_ANNUAL_RATE)
        if not approved:
            raise ValueError(f"DTI ratio {dti:.2%} exceeds {MAX_DTI:.0%} limit")
        loan = self.repository.create_and_disburse(account_ref, amount, DEFAULT_ANNUAL_RATE, term_months, payment)
        return {"loan_ref": str(loan.loan_ref), "monthly_payment": str(payment), "dti_ratio": float(dti.quantize(Decimal('0.0001'))), "status": "APPROVED"}

    def list_loans(self, customer_ref: UUID | None = None, account_ref: UUID | None = None) -> list[dict]:
        rows = self.repository.list(customer_ref, account_ref)
        return [{"loan_ref": str(x.loan_ref), "customer_ref": str(x.customer_ref), "account_ref": str(x.account_ref),
                 "principal": str(x.principal), "annual_rate": str(x.annual_rate), "term_months": x.term_months,
                 "monthly_payment": str(x.monthly_payment), "outstanding_balance": str(x.outstanding_balance),
                 "days_past_due": x.days_past_due, "status": x.status} for x in rows]
