import unittest
from decimal import Decimal
from uuid import uuid4
from bancocloud.domain.cards import Card, CardError

class CardDomainTests(unittest.TestCase):
    def test_credit_limit(self):
        c = Card(uuid4(), uuid4(), uuid4(), 'CREDIT', '4412', Decimal('15000'), Decimal('1420.50'), 'ACTIVE')
        self.assertEqual(c.validate_credit_purchase(Decimal('250')), Decimal('1670.50'))
        with self.assertRaises(CardError): c.validate_credit_purchase(Decimal('14000'))

if __name__ == '__main__': unittest.main()
