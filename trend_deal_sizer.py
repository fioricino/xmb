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

        if 'trend_days' in kwargs:
            self._trend_days = int(kwargs['trend_days'])
        else:
            self._trend_days = 7

        if 'trend_rolling_window' in kwargs:
            self._trend_rolling_window = int(kwargs['trend_rolling_window'])
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

    def get_deal_size(self, price, profile):
        try:
            ds = self._deals_provider.get_deals()
            delta = timedelta(days=self._trend_days).total_seconds()
            start_time = self._get_time() - delta
            deals = [d for d in ds if d['date'] > start_time]
            prices = [float(p['price']) for p in deals]
            deals_df = pd.DataFrame(deals).convert_objects(convert_numeric=True)
            deals_df['mean'] = deals_df['price'].rolling(self._trend_rolling_window).mean()
            last_deal = deals_df.iloc[-1]
            der_delta = timedelta(hours=self._trend_diff_hours).total_seconds()
            start_time = int(last_deal['date']) - der_delta
            first_deal = deals_df[deals_df['date'] >= start_time].iloc[0]
            price_diff = (last_deal['price'] - first_deal['price']) / first_deal['price']
            mult_base = abs(price_diff) * self._trend_multiplier + 1
            if profile == 'UP' and price_diff >= 0 or profile == 'DOWN' and price_diff <= 0:
                mult = mult_base
            else:
                mult = 1 / mult_base

            return max(mult * self._currency_1_deal_size, self._currency_1_min_deal_size)
        except:
            logger.exception('Cannot calculate deal size')
            return self._currency_1_deal_size

    def _get_time(self):
        return int(time.time())
