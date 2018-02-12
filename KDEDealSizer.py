import logging
import time
from datetime import timedelta

import numpy as np
from sklearn.neighbors import KernelDensity

logger = logging.getLogger('xmb')


class KDEDealSizer:
    def __init__(self, deals_provider, avg_price_provider, **kwargs):
        self._deals_provider = deals_provider
        self._avg_price_provider = avg_price_provider
        if 'kde_multiplier' in kwargs:
            self._kde_multiplier = float(kwargs['kde_multiplier'])
        else:
            self._kde_multiplier = 1

        if 'kde_bandwith' in kwargs:
            self._kde_bandwith = float(kwargs['kde_bandwith'])
        else:
            self._kde_bandwith = 150

        if 'kde_days' in kwargs:
            self._kde_days = int(kwargs['kde_days'])
        else:
            self._kde_days = 7

        if 'currency_1_deal_size' in kwargs:
            self._currency_1_deal_size = kwargs['currency_1_deal_size']
        else:
            self._currency_1_deal_size = 0.001

    def get_deal_size(self):
        try:
            ds = self._deals_provider.get_deals()
            delta = timedelta(days=self._kde_days).total_seconds()
            start_time = self._get_time() - delta
            deals = [d for d in ds if int(d['date']) > start_time]
            prices = [float(p['price']) for p in deals]
            pr_array = np.array(prices)
            pr_reshaped = pr_array.reshape(len(prices), 1)
            kde = KernelDensity(kernel='gaussian', bandwidth=self._kde_bandwith).fit(pr_reshaped)
            avg_price = self._avg_price_provider.get_avg_price()
            score = np.exp(kde.score(np.array(avg_price).reshape(1, 1)))
            pdf = score * (max(prices) - min(prices)) * self._kde_multiplier
            return pdf * self._currency_1_deal_size
        except:
            logger.exception('Cannot calculate deal size')
            return self._currency_1_deal_size

    def _get_time(self):
        return int(time.time())
