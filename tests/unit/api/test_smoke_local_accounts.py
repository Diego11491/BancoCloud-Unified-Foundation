import unittest
from decimal import Decimal

from scripts.smoke_local import select_accounts


class SmokeAccountSelectionTests(unittest.TestCase):
    def test_selects_funded_source_and_different_active_destination(self):
        accounts = [
            {"account_ref": "low", "balance": "675.00", "status": "ACTIVE"},
            {"account_ref": "rich", "balance": "19325.00", "status": "ACTIVE"},
            {"account_ref": "other", "balance": "10000.00", "status": "ACTIVE"},
        ]

        source, destination = select_accounts(accounts, Decimal("3075.00"))

        self.assertEqual(source["account_ref"], "rich")
        self.assertEqual(destination["account_ref"], "low")

    def test_ignores_inactive_or_invalid_accounts(self):
        accounts = [
            {"account_ref": "inactive", "balance": "50000.00", "status": "BLOCKED"},
            {"account_ref": "invalid", "balance": "not-a-number", "status": "ACTIVE"},
            {"account_ref": "source", "balance": "4000.00", "status": "ACTIVE"},
            {"account_ref": "destination", "balance": "100.00", "status": "ACTIVE"},
        ]

        source, destination = select_accounts(accounts, Decimal("3075.00"))

        self.assertEqual(source["account_ref"], "source")
        self.assertEqual(destination["account_ref"], "destination")

    def test_rejects_when_no_account_has_enough_balance(self):
        accounts = [
            {"account_ref": "one", "balance": "100.00", "status": "ACTIVE"},
            {"account_ref": "two", "balance": "200.00", "status": "ACTIVE"},
        ]

        with self.assertRaisesRegex(RuntimeError, "required balance"):
            select_accounts(accounts, Decimal("3075.00"))


if __name__ == "__main__":
    unittest.main()
