import logging

logging.basicConfig(level=logging.DEBUG)
import unittest
import numpy as np
import pandas as pd
import random

from exmo_general import Profiles
from trend_analyze import TrendAnalyzer

import warnings

warnings.simplefilter('ignore', np.RankWarning)


class TestAnalyze(unittest.TestCase):
    def test_switching_linear_pos(self):
        ta = TrendAnalyzer(rolling_window=6, profit_multiplier=0.5, mean_price_period=10, price_period=None)
        ta._current_time = lambda: 20
        profile, profit_markup, mean_price = ta.get_profile([{'date': str(i), 'trade_id': str(i),
                                                  'price': str(1200 + 10 * i)} for i in range(20)])
        self.assertEqual(Profiles.UP, profile)
        self.assertGreater(profit_markup, 0)

    def test_switching_linear_neg(self):
        ta = TrendAnalyzer(rolling_window=6, profit_multiplier=0.5, mean_price_period=10, price_period=None)
        ta._current_time = lambda: 20
        deals = [{'date': str(i), 'trade_id': str(i), 'price': str(1200 - 10 * i)} for i in range(20)]
        ta._current_time = lambda: 20
        profile, profit_markup, mean_price = ta.get_profile(
            deals)
        self.assertEqual(Profiles.DOWN, profile)
        self.assertGreater(profit_markup, 0)

    def test_switching_linear_neg_interpolation(self):
        ta = TrendAnalyzer(rolling_window=6, profit_multiplier=0.5, mean_price_period=10, price_period=None)
        ta._current_time = lambda: 20
        profile, profit_markup, mean_price = ta.get_profile(
            [{'date': str(i), 'trade_id': str(i), 'price': str(1200 - 10 * i)} for i in
             [1, 2, 3, 3, 5, 8, 9, 10, 10, 12, 14, 15, 15, 17, 18, 21, 22, 23]])
        self.assertEqual(Profiles.DOWN, profile)
        self.assertGreater(profit_markup, 0)

    def test_switching_linear_neg_interpolation_shuffled(self):
        ta = TrendAnalyzer(rolling_window=6, profit_multiplier=0.5, mean_price_period=10, price_period=None)
        deals = [{'date': str(i), 'trade_id': str(i), 'price': str(1200 - 10 * i)} for i in
                 [1, 2, 3, 3, 5, 8, 9, 10, 10, 12, 14, 15, 15, 17, 18, 21, 22, 23]]
        ta._current_time = lambda: 20
        random.shuffle(deals)
        profile, profit_markup, mean_price = ta.get_profile(
            deals)
        self.assertEqual(Profiles.DOWN, profile)
        self.assertGreater(profit_markup, 0)

    def test_switching_sinus(self):
        # see graph in PriceData.ipynb
        ta = TrendAnalyzer(rolling_window=6, profit_multiplier=2, mean_price_period=10, price_period=None)
        ta._current_time = lambda: 240
        price_period = 1
        start_index = 0

        x = pd.DataFrame(np.arange(240))
        # исходная функция - синусоида
        source_price_func = lambda x: 12000 + 200 * np.sin(0.05 * x)
        # добавим нормальное распределение
        randomized_price_func = np.random.normal(source_price_func(x), 10)

        all_prices = [{'date': str(i), 'trade_id': str(i), 'price': str(p[0])} for i, p in
                      enumerate(randomized_price_func)]

        for i in range(len(all_prices) - 100):
            last_index = min(start_index + 100, len(all_prices) - 1)
            prices = all_prices[start_index:last_index]
            start_index += price_period
            ta._current_time = lambda: last_index
            profile, profit_markup, mean_price = ta.get_profile(prices)
            logging.debug('{} {}'.format(profile, profit_markup))
            last_price = int(all_prices[last_index]['date'])
            if last_price in range(19, 37) or last_price in range(105, 159) or last_price in range(230, 250):
                self.assertEqual(Profiles.UP, profile)
            elif last_price in range(42, 98) or last_price in range(166, 226):
                self.assertEqual(Profiles.DOWN, profile)

    def test_switching_sinus_interpolation(self):
        # see graph in PriceData.ipynb
        ta = TrendAnalyzer(rolling_window=6, profit_multiplier=2, mean_price_period=10, price_period=None)
        ta._current_time = lambda: 1240
        price_period = 1
        start_index = 0

        x = pd.DataFrame([round(np.random.normal(i + 1000, 1)) for i in np.arange(240)])
        # исходная функция - синусоида
        source_price_func = lambda x: 12000 + 200 * np.sin(0.05 * x)
        # добавим нормальное распределение
        randomized_price_func = np.random.normal(source_price_func(x), 10)

        all_prices = [{'date': str(i), 'trade_id': str(i), 'price': str(p[0])} for i, p in
                      enumerate(randomized_price_func)]

        for i in range(len(all_prices) - 100):
            last_index = min(start_index + 100, len(all_prices) - 1)
            prices = all_prices[start_index:last_index]
            start_index += price_period
            ta._current_time = lambda: last_index
            profile, profit_markup, mean_price = ta.get_profile(prices)
            logging.debug('{} {}'.format(profile, profit_markup))
            last_price = int(all_prices[last_index]['date'])
            if last_price in range(19, 37) or last_price in range(110, 159) or last_price in range(236, 250):
                self.assertEqual(Profiles.UP, profile)
            elif last_price in range(42, 98) or last_price in range(172, 226):
                self.assertEqual(Profiles.DOWN, profile)


if __name__ == '__main__':
    unittest.main()
