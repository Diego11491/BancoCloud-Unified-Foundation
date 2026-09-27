from typing import Protocol
from uuid import UUID
from bancocloud.domain.loans import Loan


class LoanRepository(Protocol):
    def list(self, customer_ref: UUID | None = None, account_ref: UUID | None = None) -> list[Loan]: ...
    def create_and_disburse(self, account_ref: UUID, principal, annual_rate, term_months: int, monthly_payment) -> Loan: ...
