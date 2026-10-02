from decimal import Decimal
from uuid import UUID
from bancocloud.domain.cards import Card
from bancocloud.infrastructure.postgres.connection import connect


_SELECT = "SELECT card_ref,account_ref,customer_ref,card_type,last_four,credit_limit,used_balance,status FROM cards"


def _card(row) -> Card:
    return Card(
        card_ref=row[0], account_ref=row[1], customer_ref=row[2], card_type=row[3], last_four=row[4],
        credit_limit=Decimal(row[5]) if row[5] is not None else None,
        used_balance=Decimal(row[6]), status=row[7],
    )


class PostgresCardRepository:
    def list(self, customer_ref: UUID | None = None, account_ref: UUID | None = None) -> list[Card]:
        clauses, params = [], []
        if customer_ref:
            clauses.append("customer_ref=%s"); params.append(customer_ref)
        if account_ref:
            clauses.append("account_ref=%s"); params.append(account_ref)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with connect() as conn:
            rows = conn.execute(_SELECT + where + " ORDER BY issued_at DESC LIMIT 20", tuple(params)).fetchall()
        return [_card(r) for r in rows]

    def purchase_credit(self, card_ref: UUID, expected_customer_ref: UUID, amount: Decimal) -> Card:
        with connect() as conn:
            with conn.transaction():
                row = conn.execute(_SELECT + " WHERE card_ref=%s FOR UPDATE", (card_ref,)).fetchone()
                if not row:
                    raise LookupError("Card not found")
                card = _card(row)
                if card.customer_ref != expected_customer_ref:
                    raise PermissionError("Card belongs to another customer")
                card.validate_credit_purchase(amount)
                conn.execute("UPDATE cards SET used_balance=used_balance+%s WHERE card_ref=%s", (amount, card_ref))
                updated = Card(card.card_ref, card.account_ref, card.customer_ref, card.card_type, card.last_four,
                               card.credit_limit, card.used_balance + amount, card.status)
        return updated

    def get_for_update(self, card_ref: UUID) -> Card | None:
        with connect() as conn:
            row = conn.execute(_SELECT + " WHERE card_ref=%s", (card_ref,)).fetchone()
        return _card(row) if row else None

    def add_used_balance(self, card_ref: UUID, amount: Decimal) -> None:
        with connect() as conn:
            conn.execute("UPDATE cards SET used_balance=used_balance+%s WHERE card_ref=%s", (amount, card_ref))