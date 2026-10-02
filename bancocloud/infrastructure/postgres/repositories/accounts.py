from decimal import Decimal
from uuid import UUID
from bancocloud.domain.accounts import Account
from bancocloud.infrastructure.postgres.connection import connect


class PostgresAccountRepository:
    def list_by_customer(self, customer_ref: UUID) -> list[Account]:
        with connect() as conn:
            rows = conn.execute(
                "SELECT account_ref,customer_ref,balance,status FROM accounts WHERE customer_ref=%s ORDER BY account_ref",
                (customer_ref,),
            ).fetchall()
        return [Account(r[0], r[1], Decimal(r[2]), r[3]) for r in rows]

    def list_all(self, limit: int = 10) -> list[Account]:
        limit = max(1, min(int(limit), 100))
        with connect() as conn:
            rows = conn.execute(
                "SELECT account_ref,customer_ref,balance,status FROM accounts ORDER BY account_ref LIMIT %s",
                (limit,),
            ).fetchall()
        return [Account(r[0], r[1], Decimal(r[2]), r[3]) for r in rows]

    def movements(self, account_ref: UUID, customer_ref: UUID, limit: int = 50) -> list[dict]:
        limit = max(1, min(int(limit), 100))
        with connect() as conn:
            acc = conn.execute("SELECT customer_ref FROM accounts WHERE account_ref=%s", (account_ref,)).fetchone()
            if not acc:
                raise LookupError("Account not found")
            if acc[0] != customer_ref:
                raise PermissionError("Account belongs to another customer")

            rows = conn.execute(
                "SELECT transaction_id,source_account,destination_account,amount,correlation_id,created_at "
                "FROM transactions WHERE source_account=%s OR destination_account=%s "
                "ORDER BY created_at DESC LIMIT %s",
                (account_ref, account_ref, limit),
            ).fetchall()
        return [
            {
                "transaction_id": str(r[0]),
                "source_account": str(r[1]),
                "destination_account": str(r[2]),
                "amount": str(r[3]),
                "correlation_id": str(r[4]),
                "created_at": r[5].isoformat(),
                "type": "expense" if r[1] == account_ref else "income",
            }
            for r in rows
        ]
