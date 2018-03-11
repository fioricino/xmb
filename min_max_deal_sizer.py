deals_df['max'] = de
from datetime import timedelta

import pandas as pd


class MinMaxDealSizer:


def __init__(self, deals_provider, **kwargs):
    self._deals_provider = deals_provider


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
        max_price = limit_deals['price'].max()
        min_price = limit_deals['price'].min()
        last_deal = deals_df.iloc[-1]
        der_delta = timedelta(hours=self._trend_diff_hours).total_seconds()
        start_time = int(last_deal['date']) - der_delta
        first_deal = deals_df[deals_df['date'] >= start_time].iloc[0]
        mean_price_diff = (last_deal['mean'] - first_deal['mean']) / first_deal['mean']
        if mean_price_diff > 0:
            # how far is price above min?
            price_diff = last_deal['mean'] - min_price
            if price_diff > self._price_limit_diff:
                # create up reserve orders, down profit orders
                pass

except:
