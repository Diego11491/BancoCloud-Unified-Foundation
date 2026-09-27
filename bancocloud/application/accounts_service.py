from uuid import UUID
from bancocloud.repositories.accounts import AccountRepository


class AccountsService:
    def __init__(self, repository: AccountRepository): self.repository = repository

    def list_accounts(self, customer_ref: UUID | None = None) -> list[dict]:
        accounts = self.repository.list_by_customer(customer_ref) if customer_ref else self.repository.list_all()
        return [{"account_ref": str(a.account_ref), "customer_ref": str(a.customer_ref), "balance": str(a.balance), "status": a.status}
                for a in accounts]

    def movements(self, account_ref: UUID, limit: int = 50) -> list[dict]:
        return self.repository.movements(account_ref, limit)
