import logging
import math
import time
from datetime import timedelta

import numpy as np
from scipy.stats import gaussian_kde

logger = logging.getLogger('xmb')


class KDEDealSizer:
    def __init__(self, deals_provider, **kwargs):
        self._deals_provider = deals_provider
        if 'kde_multiplier' in kwargs:
            self._kde_multiplier = float(kwargs['kde_multiplier'])
        else:
            self._kde_multiplier = 5

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

    def get_deal_size(self, price, profile):
        try:
            ds = self._deals_provider.get_deals()
            delta = timedelta(days=self._kde_days).total_seconds()
            start_time = self._get_time() - delta
            deals = [d for d in ds if int(d['date']) > start_time]
            prices = [float(p['price']) for p in deals]
            pr_array = np.array(prices)
            # pr_reshaped = pr_array.reshape(len(prices), 1)
            # kde = KernelDensity(kernel='gaussian', bandwidth=self._kde_bandwith).fit(pr_reshaped)
            kde = gaussian_kde(prices, bw_method=self._kde_bandwith / pr_array.std(ddof=1))
            if profile == 'UP':
                left = price
                right = math.inf
            elif profile == 'DOWN':
                left = 0
                right = price
            else:
                raise ValueError('Profile {} not supported'.format(profile))
            cdf = kde.integrate_box_1d(left, right)
            cdf_mult = cdf * self._kde_multiplier
            # score = np.exp(kde.score(np.array(avg_price).reshape(1, 1)))
            # pdf = score * (max(prices) - min(prices)) * self._kde_multiplier
            return max(self._currency_1_deal_size, cdf_mult * self._currency_1_deal_size)
        except:
            logger.exception('Cannot calculate deal size')
            return self._currency_1_deal_size

    def _get_time(self):
        return int(time.time())
