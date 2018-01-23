import logging
import time

import numpy as np
import pandas as pd
import scipy.misc as sp

from exmo_general import Profiles


class TrendAnalyzer:
    def __init__(self, rolling_window, profit_multiplier, price_period, currency_1='BTC', currency_2='USD',
                 stock_time_offset=0):
        self._currency_1 = currency_1
        self._currency_2 = currency_2
        self._stock_time_offset = stock_time_offset
        self._rolling_window = rolling_window
        # TODO change if derivative is large??
        self._price_period = price_period
        self.profit_multiplier = profit_multiplier

    def _get_prices_for_period(self, deals):
        sorted_deals = sorted([d for d in deals if
                               self._price_period is None or time.time() + self._stock_time_offset * 60 * 60 - int(
                                   d['date']) < self._price_period], key=lambda dl: int(dl['trade_id']))
        return [float(d['price']) for d in sorted_deals]

    def _get_derivative_func(self, deals):
        # TODO make function(time)!!!
        deals_df = pd.DataFrame([p for p in deals])
        # TODO calculate with amount
        mean_price = deals_df.mean()
        normalized_prce_func = deals_df / mean_price
        rolling_mean_price_func = normalized_prce_func.rolling(self._rolling_window).mean()[0]
        derivative_func = [sp.derivative(lambda x: rolling_mean_price_func[x], i) for i in range(1, len(deals) - 1)]
        rolling_mean_derivative_func = pd.DataFrame(derivative_func).rolling(self._rolling_window).mean()
        return rolling_mean_derivative_func[0]

    def get_profile(self, trades):
        last_deals = self._get_prices_for_period(trades)
        derivative_func = self._get_derivative_func(last_deals)
        index = -1
        last_derivative = derivative_func.iloc[index]
        profit_markup = abs(self.profit_multiplier * last_derivative)
        logging.debug('Deal time: {}. Deal id: {}. Last derivative: {}. Profit markup: {}.'.format(
            time.ctime(int(trades[-1]['date'])), trades[-1]['trade_id'], last_derivative, profit_markup
        ))
        if np.math.isnan(last_derivative):
            return None, None
        if last_derivative >= 0:
            return Profiles.UP, profit_markup
        if last_derivative < 0:
            return Profiles.DOWN, profit_markup
