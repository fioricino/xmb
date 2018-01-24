import logging
import math
import time

from exceptions import ApiError


class Worker:
    def __init__(self, api,
                 storage,
                 advisor,
                 max_profit_orders_up=5,
                 max_profit_orders_down=5,
                 min_profit_orders_up=1,
                 min_profit_orders_down=1,
                 period=1,
                 currency_1='BTC',
                 currency_2='USD',
                 stock_fee=0.002,
                 profit_markup=0.001,
                 reserve_price_distribution=0.001,
                 currency_1_deal_size=0.001,
                 profit_order_price_deviation=0.02
                 ):
        self._api = api
        self._storage = storage
        self._advisor = advisor
        self._period = period
        self._interrupted = False
        self._currency_1 = currency_1
        self._currency_2 = currency_2
        self._stock_fee = stock_fee
        self._profit_markup = profit_markup
        self._reserve_price_distribution = reserve_price_distribution
        self._currency_1_deal_size = currency_1_deal_size
        self._max_profit_orders_up = max_profit_orders_up
        self._max_profit_orders_down = max_profit_orders_down
        self._min_profit_orders_up = min_profit_orders_up
        self._min_profit_orders_down = min_profit_orders_down
        self._profit_order_price_deviation = profit_order_price_deviation

    # TODO move
    def run(self):
        self._interrupted = False
        while not self._interrupted:
            try:
                self.main_flow()
                time.sleep(self._period)
            except ApiError as e:
                logging.exception('Merket api error')
            except Exception as e:
                logging.exception('Fatal exception')

    def stop(self):
        self._interrupted = True

    def main_flow(self):
        # Получаем список активных ордеров
        all_orders = self._storage.get_open_orders()
        open_orders = [o for o in all_orders if o['status'] == 'OPEN']
        wait_orders = [o for o in all_orders if o['status'] == 'WAIT_FOR_PROFIT']
        if open_orders:
            self._handle_open_orders(open_orders)
        if wait_orders:
            self._handle_orders_wait_for_profit(wait_orders)
        self._make_reserve()

    def _handle_open_orders(self, open_orders):

        try:
            market_open_orders = [order['order_id'] for order in
                              self._api.get_open_orders(self._currency_1, self._currency_2)]
            for order in open_orders:
                self._handle_open_order(market_open_orders, order)
        except Exception as e:
            logging.exception('Cannot handle open orders')

    def _handle_open_order(self, market_open_orders, order):
        try:
            if order['order_id'] in market_open_orders:
                # order still open
                if order['order_type'] == 'RESERVE':
                    # open profit orders can be ignored
                    self._handle_open_reserve_order(order)
            else:
                # order completed
                self._handle_completed_order(order)
        except Exception as e:
            logging.exception('Cannot handle order: {}'.format(order['order_id']))

    def _handle_completed_order(self, order):
        if order['order_type'] == 'PROFIT':
            # just update status in storage
            self._handle_completed_profit_order(order)
        else:
            self._handle_completed_reserve_order(order)

    def _handle_completed_profit_order(self, order):
        logging.debug('Profit order {} completed'.format(order['order_id']))
        self._storage.delete(order['order_id'], 'COMPLETED')
        self._storage.delete(order['base_order']['order_id'], 'COMPLETED')

    def _handle_completed_reserve_order(self, order):
        logging.debug('Reserve order {} completed'.format(order['order_id']))
        self._storage.update_order_status(order['order_id'], 'WAIT_FOR_PROFIT')
        self._create_profit_order(order)

    def _handle_open_reserve_order(self, order):
        is_order_partially_completed = self._api.is_order_partially_completed(order['order_id'])
        if is_order_partially_completed:
            logging.debug('Order {} is partially completed'.format(order['order_id']))
        else:
            self._check_reserve_order(order)

    def _handle_orders_wait_for_profit(self, wait_orders):
        try:
            for order in wait_orders:
                self._create_profit_order(order, self._profit_markup)
        except Exception as e:
            logging.exception('Cannot handle orders waiting for profit')

    def _check_reserve_order(self, order):
        profile, profit_markup, mean_price = self._advisor.get_advice()
        if order['profile'] == profile:
            my_need_price = self._calculate_desired_reserve_price(mean_price, profile)
            if math.fabs(my_need_price - float(order['price'])) > float(
                    order['price']) * self._reserve_price_distribution:
                logging.debug('Reserve price has changed for order {} -> {}: {}'
                              .format(order['order_id'], order['order_data']['price'], my_need_price))
                self._cancel_order(order)
        else:
            logging.debug('Profile has changed for order {}: {} -> {}'
                          .format(order['order_id'], order['profile'], profile))
            if profit_markup < self._profit_markup:
                logging.debug("Profit to small, won't cancel order {}".format(order['order_id']))
            else:
                self._cancel_order(order)

    def _cancel_order(self, order):
        self._api.cancel_order(order['order_id'])
        self._storage.delete(order['order_id'], 'CANCELED')

    def _make_reserve(self):
        try:
            profile, profit_markup, avg_price = self._advisor.get_advice()
            all_orders = self._storage.get_open_orders()
            same_profile_orders = [o for o in all_orders if o['profile'] == profile]
            same_profile_profit_orders = [o for o in same_profile_orders if o['order_type'] == 'PROFIT']
            if len(same_profile_profit_orders) >= self._get_max_open_profit_orders_limit(profile):
                logging.debug('Too much orders for profile {}: {}'.format(profile, len(same_profile_profit_orders)))
                return
            if profit_markup < self._profit_markup:
                logging.debug('Too small profit markup: {} < {}'.format(profit_markup, self._profit_markup))
                return
            # Ордер с минимальным отклонением от текущей средней цены
            min_price_diff = min(
                [abs(float(o['order_data']['price']) - avg_price) for o in same_profile_orders]) / avg_price
            # Првоеряем минимальное отклонение цены от существующих ордеров:
            if min_price_diff <= self._profit_order_price_deviation:
                logging.debug('Price deviation with other orders is too small: {} < {}'.format(min_price_diff,
                                                                                               self._profit_order_price_deviation))
                return
            self._create_reserve_order(profile, avg_price)
        except Exception as e:
            logging.exception('Cannot make reserve')

    def _create_reserve_order(self, profile, avg_price):
        my_need_price = self._calculate_desired_reserve_price(avg_price, profile)
        my_amount = self._calculate_desired_reserve_amount(profile)
        new_order_id = self._api.create_order(
            currency_1=self._currency_1,
            currency_2=self._currency_2,
            quantity=my_amount,
            price=my_need_price,
            type=self._reserve_order_type(profile)
        )
        open_orders = self._api.get_open_orders(self._currency_1, self._currency_2)
        new_order = next(order for order in open_orders if order['order_id'] == new_order_id)
        stored_order = self._storage.create_order(new_order, profile, 'RESERVE')
        logging.debug('Created new reserve order:\n{}'.format(stored_order))

    def _create_profit_order(self, base_order):
        """
                        Высчитываем курс для продажи.
                        Нам надо продать всю валюту, которую купили, на сумму, за которую купили + немного навара и минус комиссия биржи
                        При этом важный момент, что валюты у нас меньше, чем купили - бирже ушла комиссия
                        0.00134345 1.5045
                    """
        # balances = self._api.get_balances()
        profile, profit_markup, avg_price = self._advisor.get_advice()
        base_profile = base_order['profile']
        if profile != base_profile:
            logging.debug('Profile has changed: {}->{}. Will not create profit order for reserve order {}'
                          .format(base_profile, profile, base_order['order_id']))
            return
        if profit_markup < self._profit_markup:
            logging.debug('Profit markup too amall: {} < {}. Will not create profit order for reserve order {}'
                          .format(profit_markup, self._profit_markup, base_order['order_id']))
        quantity = self._calculate_profit_quantity(base_order['order_data'], base_profile, profit_markup)

        price = self._calculate_profit_price(quantity, base_order, base_profile, profit_markup)
        new_order_id = self._api.create_order(
            currency_1=self._currency_1,
            currency_2=self._currency_2,
            quantity=quantity,
            price=price,
            type=self._profit_order_type(base_profile)
        )
        open_orders = self._api.get_open_orders(self._currency_1, self._currency_2)
        new_order = next(order for order in open_orders if order['order_id'] == new_order_id)
        stored_order = self._storage.create_order(new_order, base_profile, 'PROFIT', base_order)
        self._storage.update_order_status(base_order['order_id'], 'PROFIT_ORDER_CREATED')
        logging.debug('Created new profit order: {}'.format(stored_order))

    def _profit_order_type(self, profile):
        if profile == 'UP':
            return 'sell'
        elif profile == 'DOWN':
            return 'buy'
        raise ValueError('Unrecognized profile: ' + profile)

    def _reserve_order_type(self, profile):
        if profile == 'UP':
            return 'buy'
        elif profile == 'DOWN':
            return 'sell'
        raise ValueError('Unrecognized profile: ' + profile)

    def _calculate_desired_reserve_amount(self, profile):
        if profile == 'UP':
            return self._currency_1_deal_size / (1 - self._stock_fee)
        elif profile == 'DOWN':
            return self._currency_1_deal_size
        raise ValueError('Unrecognized profile: ' + profile)

    def _calculate_desired_reserve_price(self, avg_price, profile):
        if profile == 'UP':
            # хотим купить подешевле
            return avg_price / (1 + self._stock_fee)
        if profile == 'DOWN':
            # хотим продать подороже
            return avg_price / (1 - self._stock_fee)
        raise ValueError('Unrecognized profile: ' + profile)

    def _calculate_profit_quantity(self, base_order, profile, profit_markup):
        amount_in_order = float(base_order['quantity'])
        if profile == 'UP':
            # Учитываем комиссию
            return amount_in_order * (1 - self._stock_fee)
        elif profile == 'DOWN':
            # Комиссия была в долларах
            return amount_in_order * (1 + profit_markup) / (1 - self._stock_fee)
        raise ValueError('Unrecognized profile: ' + profile)

    def _calculate_profit_price(self, quantity, base_order, profile, profit_markup):
        price_in_order = float(base_order['price'])
        amount_in_order = float(base_order['quantity'])
        if profile == 'UP':
            # Комиссия была снята в 1 валюте, считаем от цены ордера
            return (
                amount_in_order * price_in_order * (1 + profit_markup) / ((1 - self._stock_fee) * quantity))
        if profile == 'DOWN':
            return (amount_in_order * price_in_order * (1 - self._stock_fee)) / quantity
        raise ValueError('Unrecognized profile: ' + profile)

    def _get_max_open_profit_orders_limit(self, profile):
        if profile == 'UP':
            return self._max_profit_orders_up
        if profile == 'DOWN':
            return self._max_profit_orders_down
        raise ValueError('Invalid profile: ' + profile)

    def _get_min_open_profit_orders_limit(self, profile):
        if profile == 'UP':
            return self._min_profit_orders_up
        if profile == 'DOWN':
            return self._min_profit_orders_down
        raise ValueError('Invalid profile: ' + profile)
