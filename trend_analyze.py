import logging
import time

import numpy as np
import pandas as pd
import scipy.misc as sp

from exmo_general import Profiles


class TrendAnalyzer:
    def __init__(self, rolling_window, profit_multiplier, price_period,
                 interpolation_degree=20,
                 currency_1='BTC', currency_2='USD',
                 stock_time_offset=0):
        self._interpolation_degree = interpolation_degree
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
        return [{'price': float(d['price']), 'time': int(d['date'])} for d in sorted_deals]

    def _get_derivative_func(self, deals):
        # TODO make function(time)!!!
        deals_df = pd.DataFrame([p for p in deals])
        price_func = self.get_interpolated_func([d for d in deals_df['time']], [p for p in deals_df['price']])
        mean_price = price_func.mean()
        normalized_prce_func = price_func / mean_price
        # TODO calculate with amount
        rolling_mean_price_func = pd.DataFrame(normalized_prce_func).rolling(self._rolling_window).mean()[0]
        #       tt = self.get_interpolated_func([x for x, y in enumerate(rolling_mean_price_func[self._rolling_window:])],[y for y in rolling_mean_price_func[self._rolling_window:]])
        derivative_func = [sp.derivative(lambda x: rolling_mean_price_func[x], i) for i in
                           range(1, len(rolling_mean_price_func) - 1)]
        rolling_mean_derivative_func = pd.DataFrame(derivative_func).rolling(self._rolling_window).mean()
        return rolling_mean_derivative_func[0]

    def get_interpolated_func(self, x, y):
        polyfit = np.polyfit(x, y, self._interpolation_degree)
        poly1d = np.poly1d(polyfit)
        # generate point for each second
        x_lin = np.linspace(x[0], x[-1], x[-1] - x[0] + 1)
        new_func = poly1d(x_lin)
        return new_func

    def get_profile(self, trades):
        last_deals = self._get_prices_for_period(trades)
        derivative_func = self._get_derivative_func(last_deals)
        index = -1
        last_derivative = derivative_func.iloc[index]
        if np.math.isnan(last_derivative):
            return None, None
        profit_markup = abs(self.profit_multiplier * last_derivative)
        logging.debug('Deal time: {}. Deal id: {}. Last derivative: {}. Profit markup: {}.'.format(
            time.ctime(int(trades[-1]['date'])), trades[-1]['trade_id'], last_derivative, profit_markup
        ))

        if last_derivative >= 0:
            return Profiles.UP, profit_markup
        if last_derivative < 0:
            return Profiles.DOWN, profit_markup
