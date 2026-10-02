from typing import Protocol
from uuid import UUID
from bancocloud.domain.transfers import TransferCommand


class TransactionRepository(Protocol):
    def execute_transfer(self, command: TransferCommand, expected_customer_ref: UUID, idempotency_key: UUID) -> dict: ...
