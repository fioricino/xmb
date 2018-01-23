import logging

logging.basicConfig(level=logging.DEBUG)
import unittest
import numpy as np
import pandas as pd

from exmo_general import Profiles
from trend_analyze import TrendAnalyzer


class TestAnalyze(unittest.TestCase):
    def test_switching_linear_pos(self):
        ta = TrendAnalyzer(rolling_window=6, profit_multiplier=0.5, price_period=None)
        profile, profit_markup = ta.get_profile([{'date': str(i), 'trade_id': str(i),
                                                  'price': str(1200 + 10 * i)} for i in range(20)])
        self.assertEqual(Profiles.UP, profile)
        self.assertGreater(profit_markup, 0)

    def test_switching_linear_neg(self):
        ta = TrendAnalyzer(rolling_window=6, profit_multiplier=0.5, price_period=None)
        profile, profit_markup = ta.get_profile(
            [{'date': str(i), 'trade_id': str(i), 'price': str(1200 - 10 * i)} for i in range(20)])
        self.assertEqual(Profiles.DOWN, profile)
        self.assertGreater(profit_markup, 0)

    def test_switching_sinus(self):
        # see graph in PriceData.ipynb
        ta = TrendAnalyzer(rolling_window=6, profit_multiplier=2, price_period=None)
        price_period = 1
        start_index = 0

        x = pd.DataFrame(np.arange(240))
        # исходная функция - синусоида
        source_price_func = lambda x: 12000 + 200 * np.sin(0.05 * x)
        # добавим нормальное распределение
        randomized_price_func = np.random.normal(source_price_func(x), 10)

        all_prices = [{'date': str(i), 'trade_id': str(i), 'price': str(p[0])} for i, p in
                      enumerate(randomized_price_func)]

        for i in range(len(all_prices) - 20):
            last_index = min(start_index + 20, len(all_prices) - 1)
            prices = all_prices[start_index:last_index]
            start_index += price_period
            profile, profit_markup = ta.get_profile(prices)
            logging.debug('{} {}'.format(profile, profit_markup))
            last_price = int(all_prices[last_index]['date'])
            if last_price in range(19, 37) or last_price in range(104, 159) or last_price in range(229, 250):
                self.assertEqual(Profiles.UP, profile)
            elif last_price in range(41, 98) or last_price in range(164, 226):
                self.assertEqual(Profiles.DOWN, profile)


if __name__ == '__main__':
    unittest.main()
