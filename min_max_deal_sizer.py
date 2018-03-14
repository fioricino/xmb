import time
from datetime import timedelta

import pandas as pd


class MinMaxDealSizer:
    def __init__(self, deals_provider, **kwargs):
        self._deals_provider = deals_provider

        if 'trend_days' in kwargs:
            self._trend_days = int(kwargs['trend_days'])
        else:
            self._trend_days = 11

        if 'trend_rolling_window' in kwargs:
            self._trend_rolling_window = kwargs['trend_rolling_window']
        else:
            self._trend_rolling_window = 5000

        if 'trend_diff_hours' in kwargs:
            self._trend_diff_hours = int(kwargs['trend_diff_hours'])
        else:
            self._trend_diff_hours = 24

        if 'mean_price_period' in kwargs:
            self._mean_price_period = kwargs['mean_price_period']
        else:
            self._mean_price_period = 16

        if 'limit_days' in kwargs:
            self._limit_days = kwargs['limit_days']
        else:
            self._limit_days = 10

        if 'price_limit_diff' in kwargs:
            self._price_limit_diff = kwargs['price_limit_diff']
        else:
            self._price_limit_diff = 0.02

        self._state = None

    def get_deal_size(self):
        try:
            ds = self._deals_provider.get_deals()
            delta = timedelta(days=self._trend_days).total_seconds()
            start_time = self._get_time() - delta
            deals = [d for d in ds if d['date'] > start_time]
            deals_df = pd.DataFrame(deals).convert_objects(convert_numeric=True)
            deals_df['mean'] = deals_df.rolling(self._trend_rolling_window)['price'].mean()
            limit_start_time = self._get_time() - timedelta(days=self._limit_days).total_seconds()
            limit_deals = deals_df[deals_df['date'] >= limit_start_time]
            # max price for period
            max_price = limit_deals['mean'].max()
            # min price for period
            min_price = limit_deals['mean'].min()
            last_deal = deals_df.iloc[-1]
            der_delta = timedelta(hours=self._trend_diff_hours).total_seconds()
            start_time = int(last_deal['date']) - der_delta
            first_deal = deals_df[deals_df['date'] >= start_time].iloc[0]
            mean_price_diff = (last_deal['mean'] - first_deal['mean']) / first_deal['mean']
            avg_price = self._calculate_mean_price(deals, self._mean_price_period)
            min_price_diff = (last_deal['mean'] - min_price) / min_price
            max_price_diff = (max_price - last_deal['mean']) / max_price
            create_order = False
            profile = None
            if min_price_diff < self._price_limit_diff:
                self._state = 'MIN'
            elif max_price_diff < self._price_limit_diff:
                self._state = 'MAX'
            else:
                if self._state == 'MIN':
                    self._state = 'UP'
                    profile = 'UP'
                    create_order = True
                elif self._state == 'MAX':
                    self._state = 'DOWN'
                    profile = 'DOWN'
                    create_order = True
                elif self._state is None:
                    # TODO
                    self._state = 'UP' if mean_price_diff > 0 else 'DOWN'
                    create_order = True
                    profile = self._state
            return profile, avg_price, create_order
        except:
            return None, None, None

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
