"""Additive demo seeder for cards and loans.

It intentionally does not replace seed_db.py. Run seed_db.py first so customers/accounts exist,
then run this module after applying migration 002_cards_loans.sql.
"""
import argparse
import json
import random
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from bancocloud.domain.loans import calculate_monthly_payment
from bancocloud.infrastructure.postgres.connection import connect


def seed_products(path: str | Path, seed: int = 42) -> dict:
    rng = random.Random(seed)
    cards = loans = 0
    with Path(path).open(encoding="utf-8") as source, connect() as conn:
        with conn.transaction():
            for line in source:
                if not line.strip():
                    continue
                profile = json.loads(line)
                customer_ref = profile["customer_ref"]
                account_ref = profile["account_ref"]

                debit_ref = uuid5(NAMESPACE_URL, f"card-debit:{customer_ref}")
                debit_last_four = f"{(debit_ref.int % 9000) + 1000}"
                result = conn.execute(
                    "INSERT INTO cards(card_ref,account_ref,customer_ref,card_type,last_four,credit_limit,used_balance,status) "
                    "VALUES (%s,%s,%s,'DEBIT',%s,NULL,0,'ACTIVE') ON CONFLICT DO NOTHING RETURNING card_ref",
                    (debit_ref, account_ref, customer_ref, debit_last_four),
                ).fetchone()
                cards += int(result is not None)

                if rng.random() < 0.30:
                    credit_ref = uuid5(NAMESPACE_URL, f"card-credit:{customer_ref}")
                    credit_last_four = f"{(credit_ref.int % 9000) + 1000}"
                    credit_limit = Decimal(str(rng.choice([3000, 5000, 8000, 12000, 15000])))
                    used = (credit_limit * Decimal(str(rng.uniform(0.05, 0.65)))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    result = conn.execute(
                        "INSERT INTO cards(card_ref,account_ref,customer_ref,card_type,last_four,credit_limit,used_balance,status) "
                        "VALUES (%s,%s,%s,'CREDIT',%s,%s,%s,'ACTIVE') ON CONFLICT DO NOTHING RETURNING card_ref",
                        (credit_ref, account_ref, customer_ref, credit_last_four, credit_limit, used),
                    ).fetchone()
                    cards += int(result is not None)

                if rng.random() < 0.20:
                    loan_ref = uuid5(NAMESPACE_URL, f"loan:{customer_ref}")
                    principal = Decimal(str(rng.choice([3000, 5000, 8000, 12000, 20000])))
                    annual_rate = Decimal(str(rng.choice(["0.1499", "0.1899", "0.2399"])))
                    term = rng.choice([12, 24, 36])
                    payment = calculate_monthly_payment(principal, term, annual_rate)
                    outstanding = (principal * Decimal(str(rng.uniform(0.15, 0.95)))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    days_past_due = 0
                    status = "CURRENT"
                    if rng.random() < 0.15:
                        days_past_due = rng.choice([15, 35, 65, 95, 120])
                        status = "PAST_DUE" if days_past_due <= 90 else "DEFAULTED"
                    result = conn.execute(
                        "INSERT INTO loans(loan_ref,customer_ref,account_ref,principal,annual_rate,term_months,monthly_payment,"
                        "outstanding_balance,days_past_due,status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                        "ON CONFLICT DO NOTHING RETURNING loan_ref",
                        (loan_ref, customer_ref, account_ref, principal, annual_rate, term, payment, outstanding, days_past_due, status),
                    ).fetchone()
                    loans += int(result is not None)
    return {"cards_inserted": cards, "loans_inserted": loans}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("seed_jsonl")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    print(seed_products(args.seed_jsonl, args.seed))
