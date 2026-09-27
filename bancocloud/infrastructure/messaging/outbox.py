import json
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from bancocloud.contracts import validate
from bancocloud.domain.transfers import TransferCommand


def build_transaction_posted(*, transaction_id: UUID, customer_ref: UUID, region: str, correlation_id: UUID, command: TransferCommand) -> tuple[UUID, dict]:
    event_id = uuid4()
    event = {
        "schema_version": "1.0",
        "event_id": str(event_id),
        "event_type": "TransactionPosted",
        "event_time": datetime.now(timezone.utc).isoformat(),
        "transaction_id": str(transaction_id),
        "customer_ref": str(customer_ref),
        "account_ref": str(command.source_account),
        "transaction_type": "TRANSFER",
        "amount": float(Decimal(command.amount)),
        "currency": "PEN",
        "channel": "API",
        "authentication_method": "SESSION",
        "transaction_status": "POSTED",
        "device_ref": command.device_ref,
        "beneficiary_ref": command.beneficiary_ref,
        "location": {"country": "PE", "region": region},
        "correlation_id": str(correlation_id),
        "source_system": "core-simulator",
    }
    validate("transaction", event)
    return event_id, event


def insert_outbox(conn, event_id: UUID, transaction_id: UUID, event: dict) -> None:
    conn.execute(
        "INSERT INTO outbox_events(event_id,transaction_id,payload) VALUES (%s,%s,%s::jsonb)",
        (event_id, transaction_id, json.dumps(event)),
    )
