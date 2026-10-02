import os
import unittest
import time
import hmac
import hashlib
from uuid import uuid4
from decimal import Decimal
import psycopg

class TestCoreAuthDB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        val = os.environ.get("DATABASE_URL", "")
        if not val and os.path.exists(".env"):
            with open(".env") as f:
                for line in f:
                    if line.startswith("DATABASE_URL="):
                        val = line.split("=", 1)[1].strip()
                        break
        if not val:
            raise unittest.SkipTest("No DATABASE_URL configured")
            
        cls.admin_url = val.replace("@db:", "@127.0.0.1:").replace("@localhost:", "@127.0.0.1:")
        cls.db_name = f"bancocloud_test_{uuid4().hex}"
        cls.test_url = cls.admin_url.rsplit("/", 1)[0] + "/" + cls.db_name
        cls.original_url = os.environ.get("DATABASE_URL")
        
        created = False
        try:
            with psycopg.connect(cls.admin_url, autocommit=True) as conn:
                conn.execute(f'CREATE DATABASE "{cls.db_name}"')
            created = True
                
            with psycopg.connect(cls.test_url, autocommit=True) as conn:
                with open("infra/local/schema.sql", "r", encoding="utf-8") as f:
                    conn.execute(f.read())
                with open("infra/local/migrations/002_cards_loans.sql", "r", encoding="utf-8") as f:
                    conn.execute(f.read())
                    
            os.environ["DATABASE_URL"] = cls.test_url
            from bancocloud.api.core import app
            from fastapi.testclient import TestClient
            cls.client = TestClient(app)
        except Exception:
            if created:
                with psycopg.connect(cls.admin_url, autocommit=True) as conn:
                    conn.execute(f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{cls.db_name}' AND pid <> pg_backend_pid()")
                    conn.execute(f'DROP DATABASE IF EXISTS "{cls.db_name}"')
            raise

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'original_url'):
            if cls.original_url is not None:
                os.environ["DATABASE_URL"] = cls.original_url
            else:
                os.environ.pop("DATABASE_URL", None)
                
        if hasattr(cls, 'admin_url') and hasattr(cls, 'db_name'):
            try:
                with psycopg.connect(cls.admin_url, autocommit=True) as conn:
                    conn.execute(f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{cls.db_name}' AND pid <> pg_backend_pid()")
                    conn.execute(f'DROP DATABASE IF EXISTS "{cls.db_name}"')
            except Exception:
                pass

    def setUp(self):
        self.secret = "test-secret"
        os.environ["BFF_IDENTITY_SECRET"] = self.secret
        os.environ["DEMO_API_KEY"] = "replace-local-only"
        
    def sign(self, method, path, customer_ref, ts=None):
        import uuid
        if ts is None: ts = str(int(time.time()))
        canonical = f"{method}\n{path}\n{str(uuid.UUID(customer_ref))}\n{ts}"
        return hmac.new(self.secret.encode(), canonical.encode(), hashlib.sha256).hexdigest(), ts
        
    def _create_customer(self):
        from bancocloud.infrastructure.postgres.connection import connect
        cust_id = str(uuid4())
        with connect() as conn:
            conn.execute("INSERT INTO customers (customer_ref, region) VALUES (%s, 'US')", (cust_id,))
            conn.commit()
        return cust_id

    def _create_account(self, cust_id, balance=1000):
        from bancocloud.infrastructure.postgres.connection import connect
        acc_id = str(uuid4())
        with connect() as conn:
            conn.execute("INSERT INTO accounts (account_ref, customer_ref, balance, status) VALUES (%s, %s, %s, 'ACTIVE')", (acc_id, cust_id, balance))
            conn.commit()
        return acc_id

    def test_movements_real_repository(self):
        cust_id = self._create_customer()
        acc_id = self._create_account(cust_id)
        
        sig, ts = self.sign("GET", f"/accounts/{acc_id}/movements", cust_id)
        res = self.client.get(f"/accounts/{acc_id}/movements", headers={
            "X-Demo-Key": "replace-local-only", "X-Customer-Ref": cust_id, "X-BFF-Timestamp": ts, "X-BFF-Signature": sig
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), [])
        
        cust_id_other = self._create_customer()
        sig, ts = self.sign("GET", f"/accounts/{acc_id}/movements", cust_id_other)
        res = self.client.get(f"/accounts/{acc_id}/movements", headers={
            "X-Demo-Key": "replace-local-only", "X-Customer-Ref": cust_id_other, "X-BFF-Timestamp": ts, "X-BFF-Signature": sig
        })
        self.assertEqual(res.status_code, 403)
        
        fake_acc = str(uuid4())
        sig, ts = self.sign("GET", f"/accounts/{fake_acc}/movements", cust_id)
        res = self.client.get(f"/accounts/{fake_acc}/movements", headers={
            "X-Demo-Key": "replace-local-only", "X-Customer-Ref": cust_id, "X-BFF-Timestamp": ts, "X-BFF-Signature": sig
        })
        self.assertEqual(res.status_code, 404)
        
        res = self.client.get(f"/accounts/{acc_id}/movements", headers={
            "X-Demo-Key": "replace-local-only", "X-Customer-Ref": cust_id
        })
        self.assertEqual(res.status_code, 401)

    def test_transfer_foreign_source(self):
        from bancocloud.infrastructure.postgres.connection import connect
        cust_A = self._create_customer()
        cust_B = self._create_customer()
        source_B = self._create_account(cust_B, 1000)
        dest = self._create_account(cust_A, 0)
        
        with connect() as conn:
            tx_before = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
            outbox_before = conn.execute("SELECT COUNT(*) FROM outbox_events").fetchone()[0]
        
        sig, ts = self.sign("POST", "/transfers", cust_A)
        res = self.client.post("/transfers", json={
            "source_account": source_B, "destination_account": dest, "amount": "100.00", "device_ref": "d", "beneficiary_ref": "b"
        }, headers={
            "X-Demo-Key": "replace-local-only", "Idempotency-Key": str(uuid4()), "X-Customer-Ref": cust_A, "X-BFF-Timestamp": ts, "X-BFF-Signature": sig
        })
        
        self.assertEqual(res.status_code, 403)
        
        with connect() as conn:
            self.assertEqual(conn.execute("SELECT balance FROM accounts WHERE account_ref=%s", (source_B,)).fetchone()[0], Decimal("1000.00"))
            self.assertEqual(conn.execute("SELECT balance FROM accounts WHERE account_ref=%s", (dest,)).fetchone()[0], Decimal("0.00"))
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0], tx_before)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM outbox_events").fetchone()[0], outbox_before)

    def test_transfer_replay_foreign(self):
        from bancocloud.infrastructure.postgres.connection import connect
        cust_A = self._create_customer()
        cust_B = self._create_customer()
        source_B = self._create_account(cust_B, 1000)
        dest = self._create_account(cust_A, 0)
        idem = str(uuid4())
        
        sig_b, ts_b = self.sign("POST", "/transfers", cust_B)
        res_b = self.client.post("/transfers", json={
            "source_account": source_B, "destination_account": dest, "amount": "100.00", "device_ref": "d", "beneficiary_ref": "b"
        }, headers={"X-Demo-Key": "replace-local-only", "Idempotency-Key": idem, "X-Customer-Ref": cust_B, "X-BFF-Timestamp": ts_b, "X-BFF-Signature": sig_b})
        self.assertEqual(res_b.status_code, 200)
        
        with connect() as conn:
            tx_before = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
            out_before = conn.execute("SELECT COUNT(*) FROM outbox_events").fetchone()[0]
            
        sig_a, ts_a = self.sign("POST", "/transfers", cust_A)
        res_a = self.client.post("/transfers", json={
            "source_account": source_B, "destination_account": dest, "amount": "100.00", "device_ref": "d", "beneficiary_ref": "b"
        }, headers={"X-Demo-Key": "replace-local-only", "Idempotency-Key": idem, "X-Customer-Ref": cust_A, "X-BFF-Timestamp": ts_a, "X-BFF-Signature": sig_a})
        self.assertEqual(res_a.status_code, 403)
        self.assertNotIn(source_B, res_a.text)
        self.assertNotIn(dest, res_a.text)
        self.assertNotIn("100.00", res_a.text)
        self.assertNotIn(idem, res_a.text)
        self.assertNotIn("transaction_id", res_a.text)
        self.assertNotIn("balance", res_a.text)
        
        with connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0], tx_before)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM outbox_events").fetchone()[0], out_before)
            self.assertEqual(conn.execute("SELECT balance FROM accounts WHERE account_ref=%s", (source_B,)).fetchone()[0], Decimal("900.00"))
            self.assertEqual(conn.execute("SELECT balance FROM accounts WHERE account_ref=%s", (dest,)).fetchone()[0], Decimal("100.00"))

    def test_card_foreign(self):
        from bancocloud.infrastructure.postgres.connection import connect
        cust_A = self._create_customer()
        cust_B = self._create_customer()
        acc_B = self._create_account(cust_B)
        card_B = str(uuid4())
        with connect() as conn:
            conn.execute("INSERT INTO cards (card_ref, account_ref, customer_ref, card_type, last_four, credit_limit, used_balance, status) VALUES (%s, %s, %s, 'CREDIT', '1234', 1000, 0, 'ACTIVE')", (card_B, acc_B, cust_B))
            conn.commit()
            
        with connect() as conn:
            used_before = conn.execute("SELECT used_balance FROM cards WHERE card_ref=%s", (card_B,)).fetchone()[0]
            
        sig, ts = self.sign("POST", "/cards/purchase", cust_A)
        res = self.client.post("/cards/purchase", json={"card_ref": card_B, "amount": "50.00", "currency": "PEN"}, headers={
            "X-Demo-Key": "replace-local-only", "X-Customer-Ref": cust_A, "X-BFF-Timestamp": ts, "X-BFF-Signature": sig
        })
        self.assertEqual(res.status_code, 403)
        
        with connect() as conn:
            self.assertEqual(conn.execute("SELECT used_balance FROM cards WHERE card_ref=%s", (card_B,)).fetchone()[0], used_before)

    def test_loan_foreign(self):
        from bancocloud.infrastructure.postgres.connection import connect
        cust_A = self._create_customer()
        cust_B = self._create_customer()
        acc_B = self._create_account(cust_B, 1000)
        
        with connect() as conn:
            bal_before = conn.execute("SELECT balance FROM accounts WHERE account_ref=%s", (acc_B,)).fetchone()[0]
            loans_before = conn.execute("SELECT COUNT(*) FROM loans").fetchone()[0]
        
        sig, ts = self.sign("POST", "/loans/apply", cust_A)
        res = self.client.post("/loans/apply", json={"account_ref": acc_B, "amount": "50.00", "term_months": 12, "monthly_income": "1000.00"}, headers={
            "X-Demo-Key": "replace-local-only", "X-Customer-Ref": cust_A, "X-BFF-Timestamp": ts, "X-BFF-Signature": sig
        })
        self.assertEqual(res.status_code, 403)
        
        with connect() as conn:
            self.assertEqual(conn.execute("SELECT balance FROM accounts WHERE account_ref=%s", (acc_B,)).fetchone()[0], bal_before)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM loans").fetchone()[0], loans_before)

if __name__ == "__main__":
    unittest.main()
