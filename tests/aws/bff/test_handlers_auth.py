import unittest
from unittest.mock import patch, MagicMock
from src.aws.bff.handlers.accounts import handler as accounts_handler

class TestBffAuth(unittest.TestCase):
    @patch('src.aws.bff.handlers.accounts.client.request')
    def test_claim_present_identity_sent(self, mock_request):
        mock_request.return_value = {"status": "ok"}
        event = {
            "routeKey": "GET /accounts/{account_ref}/movements",
            "pathParameters": {"account_ref": "acc-123"},
            "requestContext": {"authorizer": {"jwt": {"claims": {"sub": "user1", "customer_ref": "cust-123"}}}}
        }
        res = accounts_handler(event, None)
        self.assertEqual(res["statusCode"], 200)
        mock_request.assert_called_once()
        self.assertEqual(mock_request.call_args[1]["customer_ref"], "cust-123")

    def test_absence_of_identity_rejected(self):
        event = {
            "routeKey": "GET /accounts/{account_ref}/movements",
            "pathParameters": {"account_ref": "acc-123"},
            "requestContext": {"authorizer": {"jwt": {"claims": {"sub": "user1"}}}} # missing customer_ref
        }
        res = accounts_handler(event, None)
        self.assertEqual(res["statusCode"], 401)
        self.assertIn("customer_ref claim missing", res["body"])

    @patch('src.aws.bff.handlers.accounts.client.request')
    def test_body_customer_ref_ignored(self, mock_request):
        mock_request.return_value = {"status": "ok"}
        event = {
            "routeKey": "GET /accounts",
            "body": '{"customer_ref": "malicious"}',
            "requestContext": {"authorizer": {"jwt": {"claims": {"sub": "user1", "customer_ref": "cust-123"}}}}
        }
        res = accounts_handler(event, None)
        self.assertEqual(res["statusCode"], 200)
        mock_request.assert_called_once()
        self.assertEqual(mock_request.call_args[1]["customer_ref"], "cust-123")
