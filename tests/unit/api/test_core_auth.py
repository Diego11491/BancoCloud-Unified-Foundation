import os
import unittest
import time
import hmac
import hashlib
from uuid import uuid4
from unittest.mock import patch
from fastapi.testclient import TestClient

from bancocloud.api.core import app


class TestCoreAuth(unittest.TestCase):
    def setUp(self):
        self.secret = "test-secret"
        os.environ["BFF_IDENTITY_SECRET"] = self.secret
        os.environ["DEMO_API_KEY"] = "replace-local-only"
        
        # Load .env for DATABASE_URL
        if os.path.exists(".env"):
            with open(".env") as f:
                for line in f:
                    if line.startswith("DATABASE_URL="):
                        val = line.split("=", 1)[1].strip()
                        os.environ["DATABASE_URL"] = val.replace("@db:", "@localhost:")
                        break
                        
        self.client = TestClient(app)
        
    def sign(self, method, path, customer_ref, ts=None):
        if ts is None: ts = str(int(time.time()))
        canonical = f"{method}\n{path}\n{customer_ref}\n{ts}"
        return hmac.new(self.secret.encode(), canonical.encode(), hashlib.sha256).hexdigest(), ts

    @patch("bancocloud.application.accounts_service.AccountsService.movements")
    def test_a_valid_signature_accepted(self, mock_movements):
        mock_movements.side_effect = LookupError("Account not found")
        # Even if account doesn't exist, we should get 404, not 401
        customer_ref = str(uuid4())
        account_ref = str(uuid4())
        path = f"/accounts/{account_ref}/movements"
        sig, ts = self.sign("GET", path, customer_ref)
        res = self.client.get(path, headers={
            "X-Demo-Key": "replace-local-only",
            "X-Customer-Ref": customer_ref,
            "X-BFF-Timestamp": ts,
            "X-BFF-Signature": sig
        })
        self.assertEqual(res.status_code, 404)
        
    def test_b_missing_signature_401(self):
        customer_ref = str(uuid4())
        path = f"/accounts/{uuid4()}/movements"
        res = self.client.get(path, headers={
            "X-Demo-Key": "replace-local-only",
            "X-Customer-Ref": customer_ref,
        })
        self.assertEqual(res.status_code, 401)
        
    def test_c_wrong_signature_401(self):
        customer_ref = str(uuid4())
        path = f"/accounts/{uuid4()}/movements"
        _, ts = self.sign("GET", path, customer_ref)
        res = self.client.get(path, headers={
            "X-Demo-Key": "replace-local-only",
            "X-Customer-Ref": customer_ref,
            "X-BFF-Timestamp": ts,
            "X-BFF-Signature": "wrong-signature"
        })
        self.assertEqual(res.status_code, 401)
        
    def test_d_tampered_customer_ref_401(self):
        customer_ref = str(uuid4())
        path = f"/accounts/{uuid4()}/movements"
        sig, ts = self.sign("GET", path, customer_ref)
        res = self.client.get(path, headers={
            "X-Demo-Key": "replace-local-only",
            "X-Customer-Ref": str(uuid4()), # Tampered!
            "X-BFF-Timestamp": ts,
            "X-BFF-Signature": sig
        })
        self.assertEqual(res.status_code, 401)
        
    def test_e_expired_timestamp_401(self):
        customer_ref = str(uuid4())
        path = f"/accounts/{uuid4()}/movements"
        ts = str(int(time.time()) - 301)
        sig, _ = self.sign("GET", path, customer_ref, ts)
        res = self.client.get(path, headers={
            "X-Demo-Key": "replace-local-only",
            "X-Customer-Ref": customer_ref,
            "X-BFF-Timestamp": ts,
            "X-BFF-Signature": sig
        })
        self.assertEqual(res.status_code, 401)
        
    def test_f_wrong_method_401(self):
        customer_ref = str(uuid4())
        path = "/transfers"
        # Signed for GET
        sig, ts = self.sign("GET", path, customer_ref)
        # Used for POST
        res = self.client.post(path, json={
            "source_account": str(uuid4()),
            "destination_account": str(uuid4()),
            "amount": "10.00",
            "device_ref": str(uuid4()),
            "beneficiary_ref": str(uuid4())
        }, headers={
            "X-Demo-Key": "replace-local-only",
            "Idempotency-Key": str(uuid4()),
            "X-Customer-Ref": customer_ref,
            "X-BFF-Timestamp": ts,
            "X-BFF-Signature": sig
        })
        self.assertEqual(res.status_code, 401)
        
    def test_g_wrong_path_401(self):
        customer_ref = str(uuid4())
        path1 = f"/accounts/{uuid4()}/movements"
        path2 = f"/accounts/{uuid4()}/movements"
        sig, ts = self.sign("GET", path1, customer_ref)
        res = self.client.get(path2, headers={
            "X-Demo-Key": "replace-local-only",
            "X-Customer-Ref": customer_ref,
            "X-BFF-Timestamp": ts,
            "X-BFF-Signature": sig
        })
        self.assertEqual(res.status_code, 401)
        
    def test_h_only_core_key_forged_ref_401(self):
        customer_ref = str(uuid4())
        path = f"/accounts/{uuid4()}/movements"
        res = self.client.get(path, headers={
            "X-Demo-Key": "replace-local-only",
            "X-Customer-Ref": customer_ref
            # Missing signature/timestamp
        })
        self.assertEqual(res.status_code, 401)

    @patch("bancocloud.application.accounts_service.AccountsService.movements")
    def test_owner_aware_movements(self, mock_movements):
        # Missing account -> LookupError -> 404
        mock_movements.side_effect = LookupError("Account not found")
        acc_ref1 = str(uuid4())
        cust_ref1 = str(uuid4())
        path1 = f"/accounts/{acc_ref1}/movements"
        sig, ts = self.sign("GET", path1, cust_ref1)
        res = self.client.get(path1, headers={
            "X-Demo-Key": "replace-local-only", "X-Customer-Ref": cust_ref1, "X-BFF-Timestamp": ts, "X-BFF-Signature": sig
        })
        self.assertEqual(res.status_code, 404)
        
        # Foreign account -> PermissionError -> 403
        mock_movements.side_effect = PermissionError("Not your account")
        acc_ref2 = str(uuid4())
        cust_ref2 = str(uuid4())
        path2 = f"/accounts/{acc_ref2}/movements"
        sig, ts = self.sign("GET", path2, cust_ref2)
        res = self.client.get(path2, headers={
            "X-Demo-Key": "replace-local-only", "X-Customer-Ref": cust_ref2, "X-BFF-Timestamp": ts, "X-BFF-Signature": sig
        })
        self.assertEqual(res.status_code, 403)
            
    @patch("bancocloud.application.cards_service.CardsService.purchase")
    def test_owner_aware_cards(self, mock_purchase):
        mock_purchase.side_effect = PermissionError("Not your card")
        cust_ref = str(uuid4())
        sig, ts = self.sign("POST", "/cards/purchase", cust_ref)
        res = self.client.post("/cards/purchase", json={"card_ref": str(uuid4()), "amount": "10.00", "currency": "PEN"}, headers={
            "X-Demo-Key": "replace-local-only", "X-Customer-Ref": cust_ref, "X-BFF-Timestamp": ts, "X-BFF-Signature": sig
        })
        self.assertEqual(res.status_code, 403)

    @patch("bancocloud.application.loans_service.LoansService.apply")
    def test_owner_aware_loans(self, mock_apply):
        mock_apply.side_effect = PermissionError("Not your account")
        cust_ref = str(uuid4())
        sig, ts = self.sign("POST", "/loans/apply", cust_ref)
        res = self.client.post("/loans/apply", json={"account_ref": str(uuid4()), "amount": "10.00", "term_months": 12, "monthly_income": "1000.00"}, headers={
            "X-Demo-Key": "replace-local-only", "X-Customer-Ref": cust_ref, "X-BFF-Timestamp": ts, "X-BFF-Signature": sig
        })
        self.assertEqual(res.status_code, 403)

    @patch("bancocloud.application.accounts_service.AccountsService.movements")
    def test_canonicalization_e2e(self, mock_movements):
        from src.aws.bff.clients.core_client import CoreClient
        import time
        mock_movements.return_value = []
        
        client = CoreClient(base_url="http://localhost:8080", api_key="replace-local-only")
        os.environ["BFF_IDENTITY_SECRET"] = "test-secret"
        
        # Upper case raw uuid
        raw_uuid = str(uuid4()).upper()
        
        # Intercept the request to just get the headers
        with patch("src.aws.bff.clients.core_client.urlopen") as mock_urlopen:
            mock_res = unittest.mock.MagicMock()
            mock_res.read.return_value = b'{"status": "ok"}'
            mock_urlopen.return_value.__enter__.return_value = mock_res
            
            client.request("GET", f"/accounts/{uuid4()}/movements", customer_ref=raw_uuid)
            req = mock_urlopen.call_args[0][0]
            
        headers = {
            "X-Demo-Key": "replace-local-only",
            "X-Customer-Ref": req.get_header("X-customer-ref"),
            "X-BFF-Timestamp": req.get_header("X-bff-timestamp"),
            "X-BFF-Signature": req.get_header("X-bff-signature")
        }
        
        # TestClient uses these headers
        res = self.client.get(req.selector, headers=headers)
        self.assertEqual(res.status_code, 200)

    @patch("bancocloud.application.transfers_service.TransfersService.transfer")
    def test_owner_aware_transfers(self, mock_transfer):
        mock_transfer.side_effect = PermissionError("Not your account")
        cust_ref = str(uuid4())
        sig, ts = self.sign("POST", "/transfers", cust_ref)
        res = self.client.post("/transfers", json={
            "source_account": str(uuid4()), "destination_account": str(uuid4()), "amount": "10.00", "device_ref": str(uuid4()), "beneficiary_ref": str(uuid4())
        }, headers={
            "X-Demo-Key": "replace-local-only", "Idempotency-Key": str(uuid4()), "X-Customer-Ref": cust_ref, "X-BFF-Timestamp": ts, "X-BFF-Signature": sig
        })
        self.assertEqual(res.status_code, 403)


if __name__ == "__main__":
    unittest.main()
