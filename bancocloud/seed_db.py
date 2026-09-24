"""Load only safe generated customer seeds; reruns leave existing demo balances alone."""
import argparse
import json
from pathlib import Path
from .db import connect


def seed(path):
    with connect() as conn, Path(path).open(encoding="utf-8") as source:
        with conn.transaction():
            for line in source:
                profile = json.loads(line)
                conn.execute("INSERT INTO customers(customer_ref,region) VALUES (%s,%s) ON CONFLICT DO NOTHING", (profile["customer_ref"],profile["departamento"]))
                conn.execute("INSERT INTO accounts(account_ref,customer_ref,balance,status) VALUES (%s,%s,%s,'ACTIVE') ON CONFLICT DO NOTHING", (profile["account_ref"],profile["customer_ref"],10000))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("seed_jsonl")
    seed(parser.parse_args().seed_jsonl)
