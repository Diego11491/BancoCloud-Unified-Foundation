import unittest
from decimal import Decimal
from bancocloud.domain.loans import calculate_monthly_payment, evaluate_dti

class LoanDomainTests(unittest.TestCase):
    def test_payment_and_dti(self):
        payment = calculate_monthly_payment(Decimal('10000'), 24)
        self.assertGreater(payment, Decimal('0'))
        approved, same_payment, dti = evaluate_dti(Decimal('10000'), 24, Decimal('5000'))
        self.assertEqual(payment, same_payment)
        self.assertTrue(approved)
        self.assertLessEqual(dti, Decimal('0.35'))

if __name__ == '__main__': unittest.main()
