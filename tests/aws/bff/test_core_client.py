import unittest
from unittest.mock import patch
import urllib.request
import os
import json
import time

from src.aws.bff.clients.core_client import CoreClient

class TestCoreClientAuth(unittest.TestCase):
    @patch('src.aws.bff.clients.core_client.urlopen')
    def test_core_client_generates_hmac_headers(self, mock_urlopen):
        mock_res = unittest.mock.MagicMock()
        mock_res.read.return_value = b'{"status": "ok"}'
        mock_urlopen.return_value.__enter__.return_value = mock_res
        
        os.environ["BFF_IDENTITY_SECRET"] = "test-secret"
        os.environ["CORE_BASE_URL"] = "http://localhost:8080"
        os.environ["CORE_API_KEY"] = "demo-key"
        
        client = CoreClient()
        with patch('time.time', return_value=1234567890.0):
            res = client.request("GET", "/test/path", customer_ref="cust-123")
            
        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.get_header("X-customer-ref"), "cust-123")
        self.assertEqual(req.get_header("X-bff-timestamp"), "1234567890")
        
        # Expected signature
        import hmac, hashlib
        expected = hmac.new(b"test-secret", b"GET\n/test/path\ncust-123\n1234567890", hashlib.sha256).hexdigest()
        self.assertEqual(req.get_header("X-bff-signature"), expected)
        self.assertEqual(res, {"status": "ok"})

if __name__ == "__main__":
    unittest.main()
