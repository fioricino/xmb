import numpy as np
import pandas as pd


class TrendReserveAdvisor:
    def __init__(self, deals_provider, storage, **kwargs):
        self._deals_provider = deals_provider
        self._current_trend = None
        self._limit_price = None
        self._current_mean_price = None
        self._avg_price = None
        self._mean_price = None

        if 'rolling_window' in kwargs:
            self._rolling_window = kwargs['rolling_window']
        else:
            self._rolling_window = 2000

        if 'limit_price_deviation' in kwargs:
            self._limit_price_deviation = kwargs['limit_price_deviation']
        else:
            self._limit_price_deviation = 0.005

        if 'same_profile_order_price_deviation' in kwargs:
            self._same_profile_order_price_deviation = kwargs['same_profile_order_price_deviation']
        else:
            self._same_profile_order_price_deviation = 0.5

        if 'currency_1' in kwargs:
            self._currency_1 = kwargs['currency_1']
        else:
            self._currency_1 = 'BTC'

        if 'currency_2' in kwargs:
            self._currency_2 = kwargs['currency_2']
        else:
            self._currency_2 = 'USD'

        if 'profit_currency_up' in kwargs:
            self._profit_currency_up = kwargs['profit_currency_up']
        else:
            self._profit_currency_up = self._currency_2

        if 'profit_currency_down' in kwargs:
            self._profit_currency_down = kwargs['profit_currency_down']
        else:
            self._profit_currency_down = self._currency_1

        if 'stock_fee' in kwargs:
            self._stock_fee = kwargs['stock_fee']
        else:
            self._stock_fee = 0.002

        if 'profit_markup' in kwargs:
            self._profit_markup = kwargs['profit_markup']
        else:
            self._profit_markup = 0.001

        if 'currency_1_min_deal_size' in kwargs:
            self._currency_1_min_deal_size = kwargs['currency_1_min_deal_size']
        else:
            self._currency_1_min_deal_size = 0.001

        if 'mean_price_period' in kwargs:
            self._mean_price_period = kwargs['mean_price_period']
        else:
            self._mean_price_period = 16

    def get_profit_order(self, base_order):
        result = None, None, None
        if self._current_trend is None:
            return result

        base_profile = base_order['profile']
        quantity = self._calculate_profit_quantity(float(base_order['quantity']), base_profile, self._profit_markup)
        price = self._calculate_profit_price(quantity, float(base_order['quantity']), float(base_order['price']),
                                             base_profile, self._profit_markup)
        order_type = self._profit_order_type(base_profile)

        if base_profile == self._current_trend:
            # if base_profile == 'UP' and price < self._avg_price or base_profile == 'DOWN' and price > self._avg_price:
            return result
            # else:
            #     return price, quantity, order_type

        else:
            if base_profile == 'UP' and price > self._avg_price or base_profile == 'DOWN' and price < self._avg_price:
                return price, quantity, order_type
            else:
                return self._avg_price, quantity, order_type

    def tick(self):
        ds = self._deals_provider.get_deals()[-10000:]
        if not ds:
            return
        df = pd.DataFrame(ds).convert_objects(convert_numeric=True)
        avg_price = np.mean(df['price'][-self._mean_price_period:])
        self._avg_price = avg_price
        df['mean'] = df['price'].rolling(self._rolling_window).mean()
        row = df.iloc[-1]
        self._mean_price = row['mean']
        if self._limit_price is not None:
            der = row['mean'] - self._limit_price
            profile = 'UP' if der > 0 else 'DOWN' if der < 0 else None
            if profile is None:
                return
            if self._current_trend == profile:
                if profile == 'UP' and row['mean'] > self._limit_price or \
                                        profile == 'DOWN' and row['mean'] < self._limit_price:
                    self._limit_price = row['mean']
            else:
                big_price_change = abs(der) > self._limit_price * self._limit_price_deviation
                if big_price_change:
                    self._current_trend = profile
                    self._limit_price = row['mean']

        else:
            self._limit_price = row['mean']

    def get_profile(self):
        return self._current_trend, self._avg_price, self._mean_price

    def _calculate_profit_quantity(self, base_quantity, profile, profit_markup):
        if profile == 'UP':
            if self._profit_currency_up == self._currency_1:
                # Учитываем комиссию
                return max(self._currency_1_min_deal_size,
                           base_quantity * (1 - self._stock_fee) * (1 - self._profit_markup))
            elif self._profit_currency_up == self._currency_2:
                return max(self._currency_1_min_deal_size, base_quantity * (1 - self._stock_fee))
            else:
                raise ValueError('Profit currency {} not supported'.format(self._profit_currency_up))
        elif profile == 'DOWN':
            if self._profit_currency_down == self._currency_1:
                return max(self._currency_1_min_deal_size, base_quantity * (1 + profit_markup)) / (
                    1 - self._stock_fee)
            elif self._profit_currency_down == self._currency_2:
                return max(self._currency_1_min_deal_size, base_quantity / (1 - self._stock_fee))
            else:
                raise ValueError('Profit currency {} not supported'.format(self._profit_currency_down))

                # Комиссия была в долларах
        raise ValueError('Unrecognized profile: ' + profile)

    def _calculate_profit_price(self, quantity, base_quantity, base_price, profile, profit_markup):
        if profile == 'UP':
            if self._profit_currency_up == self._currency_1:
                # Комиссия была снята в 1 валюте, считаем от цены ордера
                return base_quantity * base_price / quantity * (1 - self._stock_fee)
            elif self._profit_currency_up == self._currency_2:
                return base_quantity * base_price * (1 + profit_markup) / (quantity * (1 - self._stock_fee))
            else:
                raise ValueError('Profit currency {} not supported'.format(self._profit_currency_up))
        if profile == 'DOWN':
            if self._profit_currency_down == self._currency_1:
                return (base_quantity * base_price * (1 - self._stock_fee)) / quantity
            elif self._profit_currency_down == self._currency_2:
                return (base_quantity * base_price * (1 - self._stock_fee) * (1 - profit_markup)) / quantity
            else:
                raise ValueError('Profit currency {} not supported'.format(self._profit_currency_down))
        raise ValueError('Unrecognized profile: ' + profile)

    def _profit_order_type(self, profile):
        if profile == 'UP':
            return 'sell'
        elif profile == 'DOWN':
            return 'buy'
        raise ValueError('Unrecognized profile: ' + profile)
