import logging
import time
from datetime import timedelta

import pandas as pd

logger = logging.getLogger('xmb')


class TrendDealSizer:
    def __init__(self, deals_provider, **kwargs):
        self._deals_provider = deals_provider
        if 'trend_multiplier' in kwargs:
            self._trend_multiplier = float(kwargs['trend_multiplier'])
        else:
            self._trend_multiplier = 10

        if 'trend_price_diff_multiplier' in kwargs:
            self._trend_price_diff_multiplier = float(kwargs['trend_price_diff_multiplier'])
        else:
            self._trend_price_diff_multiplier = 0

        if 'trend_days' in kwargs:
            self._trend_days = int(kwargs['trend_days'])
        else:
            self._trend_days = 7

        if 'profit_markup' in kwargs:
            self._profit_markup = kwargs['profit_markup']
        else:
            self._profit_markup = 0.01

        if 'trend_rolling_window' in kwargs:
            self._trend_rolling_window = kwargs['trend_rolling_window']
        else:
            self._trend_rolling_window = 5000

        if 'trend_diff_hours' in kwargs:
            self._trend_diff_hours = int(kwargs['trend_diff_hours'])
        else:
            self._trend_diff_hours = 24

        if 'currency_1_deal_size' in kwargs:
            self._currency_1_deal_size = kwargs['currency_1_deal_size']
        else:
            self._currency_1_deal_size = 0.001

        if 'currency_1_min_deal_size' in kwargs:
            self._currency_1_min_deal_size = kwargs['currency_1_min_deal_size']
        else:
            self._currency_1_min_deal_size = 0.001

        if 'mean_price_period' in kwargs:
            self._mean_price_period = kwargs['mean_price_period']
        else:
            self._mean_price_period = 16

    def get_deal_size(self):
        try:
            ds = self._deals_provider.get_deals()
            delta = timedelta(days=self._trend_days).total_seconds()
            start_time = self._get_time() - delta
            deals = [d for d in ds if d['date'] > start_time]
            prices = [float(p['price']) for p in deals]
            deals_df = pd.DataFrame(deals).convert_objects(convert_numeric=True)
            # deals_df['time'] = pd.to_datetime(deals_df['date'], unit='s')
            # deals_df = deals_df.set_index('time')
            deals_df['mean'] = deals_df['price'].rolling(self._trend_rolling_window).mean()
            last_deal = deals_df.iloc[-1]
            der_delta = timedelta(hours=self._trend_diff_hours).total_seconds()
            start_time = int(last_deal['date']) - der_delta
            first_deal = deals_df[deals_df['date'] >= start_time].iloc[0]

            mean_price_diff = (last_deal['mean'] - first_deal['mean']) / first_deal['mean']
            profile = 'UP' if mean_price_diff > 0 else 'DOWN'

            mult_base = abs(
                mean_price_diff) * self._trend_multiplier + 1
            deal_same = mult_base * self._currency_1_deal_size
            avg_price = self._calculate_mean_price(deals, self._mean_price_period)

            return profile, self._profit_markup, avg_price, deal_same
        except:
            logger.exception('Cannot calculate deal size')
            return None, None, None, None

    def _calculate_mean_price(self, deals, mean_price_period):
        prices = []
        last_deal_date = int(deals[-1]['date'])
        for deal in deals:
            time_passed = last_deal_date - int(deal['date'])
            if time_passed < mean_price_period:
                prices.append(float(deal['price']))
        if prices:
            avg_price = sum(prices) / len(prices)
            return avg_price
        return None

    def _get_time(self):
        return int(time.time())
