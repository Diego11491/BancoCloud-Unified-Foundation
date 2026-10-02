from decimal import Decimal
from uuid import UUID, uuid4
from bancocloud.domain.loans import Loan
from bancocloud.infrastructure.postgres.connection import connect

_SELECT = ("SELECT loan_ref,customer_ref,account_ref,principal,annual_rate,term_months,monthly_payment,"
           "outstanding_balance,days_past_due,status FROM loans")


def _loan(r) -> Loan:
    return Loan(r[0], r[1], r[2], Decimal(r[3]), Decimal(r[4]), r[5], Decimal(r[6]), Decimal(r[7]), r[8], r[9])


class PostgresLoanRepository:
    def list(self, customer_ref: UUID | None = None, account_ref: UUID | None = None) -> list[Loan]:
        clauses, params = [], []
        if customer_ref:
            clauses.append("customer_ref=%s"); params.append(customer_ref)
        if account_ref:
            clauses.append("account_ref=%s"); params.append(account_ref)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with connect() as conn:
            rows = conn.execute(_SELECT + where + " ORDER BY disbursed_at DESC LIMIT 20", tuple(params)).fetchall()
        return [_loan(r) for r in rows]

    def create_and_disburse(self, account_ref: UUID, expected_customer_ref: UUID, principal: Decimal, annual_rate: Decimal, term_months: int, monthly_payment: Decimal) -> Loan:
        loan_ref = uuid4()
        with connect() as conn:
            with conn.transaction():
                account = conn.execute(
                    "SELECT customer_ref FROM accounts WHERE account_ref=%s AND status='ACTIVE' FOR UPDATE", (account_ref,)
                ).fetchone()
                if not account:
                    raise LookupError("Account not found or inactive")
                customer_ref = account[0]
                if customer_ref != expected_customer_ref:
                    raise PermissionError("Account belongs to another customer")
                conn.execute(
                    "INSERT INTO loans(loan_ref,customer_ref,account_ref,principal,annual_rate,term_months,monthly_payment,"
                    "outstanding_balance,days_past_due,status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,0,'CURRENT')",
                    (loan_ref, customer_ref, account_ref, principal, annual_rate, term_months, monthly_payment, principal),
                )
                conn.execute("UPDATE accounts SET balance=balance+%s WHERE account_ref=%s", (principal, account_ref))
        return Loan(loan_ref, customer_ref, account_ref, principal, annual_rate, term_months, monthly_payment, principal, 0, "CURRENT")
