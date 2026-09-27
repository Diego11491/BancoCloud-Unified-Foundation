from uuid import NAMESPACE_URL, uuid4, uuid5
from bancocloud.infrastructure.postgres.connection import connect


class PostgresOnboardingRepository:
    def create(self, region: str) -> dict:
        customer_ref, account_ref = uuid4(), uuid4()
        card_ref = uuid5(NAMESPACE_URL, f"card-debit:{customer_ref}")
        last_four = f"{(card_ref.int % 9000) + 1000}"
        with connect() as conn:
            with conn.transaction():
                conn.execute("INSERT INTO customers(customer_ref,region) VALUES (%s,%s)", (customer_ref, region))
                conn.execute(
                    "INSERT INTO accounts(account_ref,customer_ref,balance,status) VALUES (%s,%s,10000,'ACTIVE')",
                    (account_ref, customer_ref),
                )
                conn.execute(
                    "INSERT INTO cards(card_ref,account_ref,customer_ref,card_type,last_four,credit_limit,used_balance,status) "
                    "VALUES (%s,%s,%s,'DEBIT',%s,NULL,0,'ACTIVE')",
                    (card_ref, account_ref, customer_ref, last_four),
                )
        return {"customer_ref": str(customer_ref), "account_ref": str(account_ref), "card_ref": str(card_ref), "last_four": last_four}
