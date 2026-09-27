import json, unittest
from src.aws.bff.common.responses import response
from src.aws.bff.handlers.transfers import handler as transfers_handler

class ResponseTests(unittest.TestCase):
    def test_response(self):
        r = response(200, {'ok': True})
        self.assertEqual(r['statusCode'], 200)
        self.assertEqual(json.loads(r['body']), {'ok': True})

    def test_transfer_handler_requires_idempotency_key_before_calling_core(self):
        result = transfers_handler({"headers": {}}, None)
        self.assertEqual(result["statusCode"], 400)
        payload = json.loads(result["body"])
        self.assertEqual(payload["error"], "missing_idempotency_key")
        self.assertIn("correlation_id", payload)

if __name__ == '__main__': unittest.main()
