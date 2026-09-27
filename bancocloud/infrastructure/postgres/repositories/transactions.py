from uuid import UUID, uuid4
from bancocloud.domain.transfers import TransferCommand, TransferError
from bancocloud.infrastructure.messaging.outbox import build_transaction_posted, insert_outbox
from bancocloud.infrastructure.postgres.connection import connect

class PostgresTransactionRepository:
    def execute_transfer(self, command: TransferCommand, idempotency_key: UUID) -> dict:
        command.validate()
        request_hash = command.request_hash()
        with connect() as conn:
            with conn.transaction():
                conn.execute("SELECT pg_advisory_xact_lock(%s)", (idempotency_key.int % (2**63),))
                existing = conn.execute(
                    "SELECT transaction_id,correlation_id,request_hash FROM transactions WHERE idempotency_key=%s",
                    (idempotency_key,),
                ).fetchone()
                if existing:
                    if existing[2] != request_hash:
                        raise TransferError("Idempotency key already used with another request")
                    return {"transaction_id": str(existing[0]), "correlation_id": str(existing[1]), "replay": True}

                ids = sorted((command.source_account, command.destination_account))
                locked = conn.execute(
                    "SELECT account_ref,customer_ref,balance,status FROM accounts "
                    "WHERE account_ref IN (%s,%s) ORDER BY account_ref FOR UPDATE", ids,
                ).fetchall()
                accounts = {row[0]: row for row in locked}
                if len(accounts) != 2 or any(accounts[x][3] != "ACTIVE" for x in ids):
                    raise TransferError("Account missing or inactive")
                if accounts[command.source_account][2] < command.amount:
                    raise TransferError("Insufficient demo balance")

                customer_ref = accounts[command.source_account][1]
                region_row = conn.execute("SELECT region FROM customers WHERE customer_ref=%s", (customer_ref,)).fetchone()
                if not region_row:
                    raise TransferError("Customer region not found")
                transaction_id, correlation_id = uuid4(), uuid4()
                conn.execute("UPDATE accounts SET balance=balance-%s WHERE account_ref=%s", (command.amount, command.source_account))
                conn.execute("UPDATE accounts SET balance=balance+%s WHERE account_ref=%s", (command.amount, command.destination_account))
                conn.execute(
                    "INSERT INTO transactions(transaction_id,idempotency_key,request_hash,customer_ref,source_account,"
                    "destination_account,amount,correlation_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (transaction_id, idempotency_key, request_hash, customer_ref, command.source_account,
                     command.destination_account, command.amount, correlation_id),
                )
                event_id, event = build_transaction_posted(
                    transaction_id=transaction_id, customer_ref=customer_ref, region=region_row[0],
                    correlation_id=correlation_id, command=command,
                )
                insert_outbox(conn, event_id, transaction_id, event)
        return {"transaction_id": str(transaction_id), "correlation_id": str(correlation_id), "replay": False}
