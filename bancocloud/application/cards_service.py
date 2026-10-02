from decimal import Decimal
from uuid import UUID
from bancocloud.repositories.cards import CardRepository


class CardsService:
    def __init__(self, repository: CardRepository): self.repository = repository

    @staticmethod
    def _view(card) -> dict:
        return {"card_ref": str(card.card_ref), "account_ref": str(card.account_ref), "customer_ref": str(card.customer_ref),
                "card_type": card.card_type, "last_four": card.last_four,
                "credit_limit": str(card.credit_limit) if card.credit_limit is not None else None,
                "used_balance": str(card.used_balance), "available_credit": str(card.available_credit) if card.available_credit is not None else None,
                "status": card.status}

    def list_cards(self, customer_ref: UUID | None = None, account_ref: UUID | None = None) -> list[dict]:
        return [self._view(c) for c in self.repository.list(customer_ref, account_ref)]

    def purchase(self, card_ref: UUID, customer_ref: UUID, amount: Decimal, currency: str = "PEN") -> dict:
        card = self.repository.purchase_credit(card_ref, customer_ref, amount)
        result = self._view(card)
        result.update({"amount": str(amount), "currency": currency, "status": "APPROVED"})
        return result
