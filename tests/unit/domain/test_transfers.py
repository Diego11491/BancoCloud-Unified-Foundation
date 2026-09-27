import unittest
import hashlib
import json
from decimal import Decimal
from uuid import uuid4
from bancocloud.domain.transfers import TransferCommand, TransferError

class TransferDomainTests(unittest.TestCase):
    def test_hash_is_deterministic_and_self_transfer_rejected(self):
        a, b = uuid4(), uuid4()
        cmd = TransferCommand(a, b, Decimal('10.00'))
        self.assertEqual(cmd.request_hash(), cmd.request_hash())
        legacy_payload = {"source_account": str(a), "destination_account": str(b), "amount": "10.00",
                          "device_ref": None, "beneficiary_ref": None}
        expected = hashlib.sha256(json.dumps(legacy_payload, sort_keys=True).encode()).hexdigest()
        self.assertEqual(cmd.request_hash(), expected)
        with self.assertRaises(TransferError): TransferCommand(a, a, Decimal('10')).validate()

if __name__ == '__main__': unittest.main()
