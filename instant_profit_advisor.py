class InstantProfitAdvisor:
    def __init__(self, **kwargs):
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

    def get_profit_order(self, base_order):
        base_profile = base_order['profile']
        quantity = self._calculate_profit_quantity(float(base_order['quantity']), base_profile, self._profit_markup)
        price = self._calculate_profit_price(quantity, float(base_order['quantity']), float(base_order['price']),
                                             base_profile, self._profit_markup)
        order_type = self._profit_order_type(base_profile)

        return price, quantity, order_type

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
