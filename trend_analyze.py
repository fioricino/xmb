import logging
import time
import warnings
from collections import defaultdict

import numpy as np
import pandas as pd
import scipy.misc as sp

logger = logging.getLogger('xmb')

class TrendAnalyzer:
    def __init__(self, rolling_window, profit_multiplier, mean_price_period,
                 interpolation_degree=20,
                 currency_1='BTC', currency_2='USD',
                 stock_time_offset=0, profit_free_weight=0):
        warnings.simplefilter('ignore', np.RankWarning)
        self._interpolation_degree = interpolation_degree
        self._currency_1 = currency_1
        self._currency_2 = currency_2
        self._stock_time_offset = stock_time_offset
        self._rolling_window = rolling_window
        # TODO change if derivative is large??
        self._profit_multiplier = profit_multiplier
        self._profit_free_weight = profit_free_weight
        self._mean_price_period = mean_price_period

    def _get_prices_for_period(self, deals):
        c = defaultdict(list)
        for deal in deals:
            c[int(deal['date'])].append(float(deal['price']))
        result = []
        for time in sorted(c):
            result.append({'time': time, 'price': np.mean(c[time])})

        return result

    def _get_derivative_func(self, deals):
        # TODO make function(time)!!!
        deals_df = pd.DataFrame([p for p in deals])
        price_func, step, x_lin = self._get_interpolated_func([d for d in deals_df['time']],
                                                              [p for p in deals_df['price']])
        normalized_prce_func = self._normalize_func(price_func)
        # TODO calculate with amount
        rolling_mean_price_func = self._get_rolling_mean_func(normalized_prce_func)
        #       tt = self.get_interpolated_func([x for x, y in enumerate(rolling_mean_price_func[self._rolling_window:])],[y for y in rolling_mean_price_func[self._rolling_window:]])
        derivative_func = self._get_der_func(rolling_mean_price_func, step)
        rolling_mean_derivative_func = self._get_rolling_mean_func(derivative_func)
        return rolling_mean_derivative_func

    def _get_der_func(self, rolling_mean_price_func, step):
        return [sp.derivative(lambda x: rolling_mean_price_func[x], i) / step for i in
                range(1, len(rolling_mean_price_func) - 1)]

    def _get_rolling_mean_func(self, normalized_prce_func):
        rolling_mean_price_func = pd.DataFrame(normalized_prce_func).rolling(self._rolling_window).mean()[0]
        return rolling_mean_price_func

    def _normalize_func(self, price_func):
        mean_price = price_func.mean()
        normalized_prce_func = price_func / mean_price
        return normalized_prce_func

    def _get_interpolated_func(self, x, y):
        polyfit = np.polyfit(x, y, self._interpolation_degree)
        poly1d = np.poly1d(polyfit)
        # generate point for each second
        x_lin = np.linspace(x[0], x[-1], 100)
        step = (x_lin[-1] - x_lin[0]) / (len(x_lin) - 1)
        new_func = poly1d(x_lin)
        return new_func, step, x_lin

    def get_profile(self, trades):
        last_deals = self._get_prices_for_period(trades)
        derivative_func = self._get_derivative_func(last_deals)
        index = -1
        last_derivative = derivative_func.iloc[index]
        if np.math.isnan(last_derivative):
            return None, None, None
        profit_markup = abs(self._profit_multiplier * last_derivative) + self._profit_free_weight
        period = self._mean_price_period
        mean_price = self._calculate_mean_price(trades, period)
        tries_count = 0
        while mean_price is None and tries_count < 10:
            period *= 2
            mean_price = self._calculate_mean_price(trades, period)
        if mean_price is None:
            raise ValueError('Cannot calculate mean price')
        logger.debug('Deal time: {}\nDeal id: {}\nLast derivative: {}\nProfit markup: {}\nMean price: {}'.format(
            time.ctime(int(trades[-1]['date'])), trades[-1]['trade_id'], last_derivative, profit_markup, mean_price
        ))

        if last_derivative >= 0:
            return 'UP', profit_markup, mean_price
        if last_derivative < 0:
            return 'DOWN', profit_markup, mean_price

    def _calculate_mean_price(self, deals, mean_price_period):
        prices = []
        for deal in deals:
            time_passed = self._current_time() + self._stock_time_offset * 60 * 60 - int(deal['date'])
            if time_passed < mean_price_period:
                prices.append(float(deal['price']))
        if prices:
            avg_price = sum(prices) / len(prices)
            return avg_price
        return None

    def _current_time(self):
        return time.time()
