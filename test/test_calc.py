import unittest
from decimal import Decimal

import calc


class TestCalc(unittest.TestCase):
    def test_calculate_profit(self):
        deals = [
            {'type': 'sell', 'quantity': 0.001, 'price': Decimal('13508.3052658'), 'amount': Decimal('13.50830526')},
            {'type': 'buy', 'quantity': 0.001, 'price': Decimal('13450'), 'amount': Decimal('13.45')}
        ]
        c = calc.calculate_profit(deals)
        self.assertAlmostEqual(Decimal('-0.0000020000000000000000416333637'), c['btc'], 8)
        self.assertAlmostEqual(Decimal('0.03128865526840000065132597'), c['usd'], 4)
        self.assertAlmostEqual(Decimal('-0.02701661053160000056239618610'), c['btc_in_usd'], 4)
        self.assertAlmostEqual(Decimal('0.00427204473680000008892978390'), c['profit'], 4)
        self.assertAlmostEqual(Decimal('0.03162531979085583744744145573'), c['profit_percent'], 4)


if __name__ == "__main__":
    unittest.main()
