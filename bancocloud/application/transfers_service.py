from uuid import UUID
from bancocloud.domain.transfers import TransferCommand
from bancocloud.repositories.transactions import TransactionRepository


class TransfersService:
    def __init__(self, repository: TransactionRepository): self.repository = repository
    def transfer(self, command: TransferCommand, idempotency_key: UUID) -> dict:
        return self.repository.execute_transfer(command, idempotency_key)
