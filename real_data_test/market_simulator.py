import json
import logging
import os

from exceptions import ApiError

logger = logging.getLogger('xmb')


class MarketSimulator:
    def __init__(self, folder, initial_btc_balance, initial_usd_balance,
                 stock_fee, initial_timestamp=None, last_deals=100):
        self.balances = {'BTC': initial_btc_balance, 'USD': initial_usd_balance}
        self.initial_balances = {'BTC': initial_btc_balance, 'USD': initial_usd_balance}
        self.balances_in_orders = {'BTC': 0, 'USD': 0}
        self.stock_fee = stock_fee
        self.index = 0
        self.orders = {}
        self.order_id = 0
        self.deals = self.read_data(folder)
        self._set_initial_timestamp(initial_timestamp)
        self._last_deals = last_deals
        self._trades = []


    def _set_initial_timestamp(self, initial_timestamp):
        if initial_timestamp is None:
            self.timestamp = int(self.deals[0]['date'])
        else:
            self.timestamp = initial_timestamp
        while self.index < 101:
            self.update_timestamp(self.timestamp + 1)

    def read_data(self, folder):
        deals = {}
        for filename in os.listdir(folder):
            with open(os.path.join(folder, filename)) as f:
                d = json.load(f)
                deals.update(d)
        return sorted(deals.values(), key=lambda v: (int(v['date']), int(v['trade_id'])))

    def get_open_orders(self, currency_1, currency_2):
        return self.orders.values()

    def is_order_partially_completed(self, order_id):
        return False

    def cancel_order(self, order_id):
        logger.debug('{}: Cancel order {}'.format(self.timestamp, order_id))
        order = self.orders[order_id]
        if order['type'] == 'buy':
            amount = float(order['price']) * float(order['quantity'])
            self.balances['USD'] += amount
            self.balances_in_orders['USD'] -= amount
        elif order['type'] == 'sell':
            amount = float(order['quantity'])
            self.balances['BTC'] += amount
            self.balances_in_orders['BTC'] -= amount
        self.orders.pop(order_id)

    def get_balances(self):
        return self.balances

    def create_order(self, currency_1, currency_2, quantity, price, type):
        logger.debug(
            '{}: Create order. Type: {}. Quantity: {}. Price: {}'.format(self.timestamp, type, quantity, price))
        if type == 'buy':
            # self.balances['BTC'] += quantity * (1 - self.stock_fee)
            amount = quantity * price
            if self.balances['USD'] < amount:
                raise ApiError('Cannot create order: too few USD')
            self.balances['USD'] -= amount
            self.balances_in_orders['USD'] += amount
        elif type == 'sell':
            if self.balances['BTC'] < quantity:
                raise ApiError('Cannot create order: too few BTC')
            self.balances['BTC'] -= quantity
            self.balances_in_orders['BTC'] += quantity
            # self.balances['USD'] += quantity * price * (1 - self.stock_fee)
        self.order_id += 1
        self.orders[str(self.order_id)] = {'order_id': str(self.order_id), 'type': type, 'quantity': str(quantity),
                                           'price': str(price), 'date': self.timestamp}
        return str(self.order_id)

    def update_timestamp(self, timestamp):
        self.timestamp = timestamp
        new_deals = []
        while int(self.deals[self.index]['date']) < timestamp:
            new_deals.append(self.deals[self.index])
            self.index += 1
        self._handle_deals(new_deals)

    def get_timestamp(self):
        return self.timestamp

    def get_max_timestamp(self):
        return int(self.deals[-1]['date'])

    def get_user_trades(self, currency_1, currency_2, offset=0, limit=100):
        return self._trades

    def get_trades(self, currency_1, currency_2):
        return self.deals[self.index - self._last_deals:self.index - 1]

    def _handle_deals(self, new_deals):
        orders_to_complete = set()
        for deal in new_deals:
            orders_to_complete.update(self._check_deal(deal))
        if orders_to_complete:
            for order_id in orders_to_complete:
                self._complete_order(self.orders[order_id])
            logger.debug('{}: Balance: {}'.format(self.timestamp, self.balances))

    def _check_deal(self, deal):
        orders_to_complete = set()
        for order_id, order in self.orders.items():
            if order['type'] == 'buy':
                if float(deal['price']) <= float(order['price']):
                    orders_to_complete.add(order_id)
            elif order['type'] == 'sell':
                if float(deal['price']) > float(order['price']):
                    orders_to_complete.add(order_id)
        return orders_to_complete

    def _complete_order(self, order):
        logger.info('{}: Complete {} order {}'.format(self.timestamp, order['type'], order['order_id']))
        if order['type'] == 'buy':
            withdrawed = float(order['quantity'])
            got = withdrawed * (1 - self.stock_fee)
            logger.info('Amount: {} BTC'.format(got))
            self.balances['BTC'] += got
            self.balances_in_orders['USD'] -= float(order['price']) * float(order['quantity'])
        elif order['type'] == 'sell':
            quantity = float(order['quantity'])
            withdrawed = quantity * float(order['price'])
            got = withdrawed * (1 - self.stock_fee)
            self.balances['USD'] += got
            self.balances_in_orders['BTC'] -= quantity
            logger.info('Amount: {} USD'.format(got))
        self.orders.pop(order['order_id'])
        self._trades.append(order)
        logger.info(
            '{}: Balance: BTC: {:.6f}, USD: {:.2f}'.format(self.timestamp, self.balances['BTC'], self.balances['USD']))
        logger.info('{}: Balance (with orders): BTC: {:.6f}, USD: {:.2f}'.format(self.timestamp, self.balances['BTC']
                                                                                 + self.balances_in_orders['BTC'],
                                                                                 self.balances['USD']
                                                                                 + self.balances_in_orders['USD']))

    def get_balances_with_orders(self):
        return {'USD': self.balances['USD']
                       + self.balances_in_orders['USD'], 'BTC': self.balances['BTC'] + self.balances_in_orders['BTC']}

    def get_profit(self):
        return {'BTC': self.balances['BTC'] - self.initial_balances['BTC'] + self.balances_in_orders['BTC'],
                'USD': self.balances['USD'] - self.initial_balances['USD'] + self.balances_in_orders['USD']}
