import logging
import math
import time
from collections import Counter
from datetime import timedelta

from exceptions import ApiError

logger = logging.getLogger('xmb')


class Lazy:
    def __init__(self, func, *params):
        self.func = func
        self.params = params
        self.initialized = False
        self.value = None

    def get_value(self):
        if self.initialized:
            return self.value
        self.value = self.func(*self.params)
        self.initialized = True
        return self.value


class Worker:
    def __init__(self, api,
                 storage,
                 advisor,
                 **kwargs):
        self._api = api
        self._storage = storage
        self._advisor = advisor
        self._interrupted = False

        if 'profit_price_avg_price_deviation' in kwargs:
            self._profit_price_avg_price_deviation = kwargs['profit_price_avg_price_deviation']
        else:
            self._profit_price_avg_price_deviation = 0.001

        if 'profit_order_lifetime' in kwargs:
            self._profit_order_lifetime = kwargs['profit_order_lifetime']
        else:
            self._profit_order_lifetime = 60

        if 'period' in kwargs:
            self._period = kwargs['period']
        else:
            self._period = 1

        if 'currency_1' in kwargs:
            self._currency_1 = kwargs['currency_1']
        else:
            self._currency_1 = 'BTC'

        if 'currency_2' in kwargs:
            self._currency_2 = kwargs['currency_2']
        else:
            self._currency_2 = 'USD'

        if 'stock_fee' in kwargs:
            self._stock_fee = kwargs['stock_fee']
        else:
            self._stock_fee = 0.002

        if 'profit_markup' in kwargs:
            self._profit_markup = kwargs['profit_markup']
        else:
            self._profit_markup = 0.001

        if 'reserve_price_avg_price_deviation' in kwargs:
            self._reserve_price_avg_price_deviation = kwargs['reserve_price_avg_price_deviation']
        else:
            self._reserve_price_avg_price_deviation = 0.001

        if 'profit_price_prev_price_deviation' in kwargs:
            self._profit_price_prev_price_deviation = kwargs['profit_price_prev_price_deviation']
        else:
            self._profit_price_prev_price_deviation = 0.0001

        if 'currency_1_deal_size' in kwargs:
            self._currency_1_deal_size = kwargs['currency_1_deal_size']
        else:
            self._currency_1_deal_size = 0.001

        if 'max_profit_orders_up' in kwargs:
            self._max_profit_orders_up = kwargs['max_profit_orders_up']
        else:
            self._max_profit_orders_up = 5

        if 'max_profit_orders_down' in kwargs:
            self._max_profit_orders_down = kwargs['max_profit_orders_down']
        else:
            self._max_profit_orders_down = 5

        if 'same_profile_order_price_deviation' in kwargs:
            self._same_profile_order_price_deviation = kwargs['same_profile_order_price_deviation']
        else:
            self._same_profile_order_price_deviation = 0.02

        if 'profit_currency_up' in kwargs:
            self._profit_currency_up = kwargs['profit_currency_up']
        else:
            self._profit_currency_up = self._currency_2

        if 'profit_currency_down' in kwargs:
            self._profit_currency_down = kwargs['profit_currency_down']
        else:
            self._profit_currency_down = self._currency_1

        if 'target_period' in kwargs:
            self._target_period = kwargs['target_period']
        else:
            self._target_period = None

        if 'target_profit' in kwargs:
            self._target_profit = kwargs['target_profit']
        else:
            self._target_profit = None

        if 'target_currency' in kwargs:
            self._target_currency = kwargs['target_currency']
        else:
            self._target_currency = self._currency_2

        if 'profit_compensation_periods' in kwargs:
            self._profit_compensation_periods = kwargs['profit_compensation_periods']
        else:
            self._profit_compensation_periods = 1

        if 'currency_1_max_deal_size' in kwargs:
            self._currency_1_max_deal_size = kwargs['currency_1_max_deal_size']
        else:
            self._currency_1_max_deal_size = 0.002

        self.profit_remainder = 0

        self._current_deal_size = self._currency_1_deal_size
        self._current_period = None


    # TODO move
    def run(self):
        self._interrupted = False
        while not self._interrupted:
            try:
                self.main_flow()
                time.sleep(self._period)
            except ApiError as e:
                logger.exception('Merket api error')
            except Exception as e:
                logger.exception('Fatal exception')

    def stop(self):
        self._interrupted = True

    def main_flow(self):
        self._check_profit()

        user_trades = Lazy(self._api.get_user_trades, self._currency_1, self._currency_2)

        open_orders = [o for o in self._storage.get_open_orders() if o['status'] == 'OPEN']

        if open_orders:
            self._handle_open_orders(open_orders, user_trades)

        wait_orders = [o for o in self._storage.get_open_orders() if
                       o['status'] == 'WAIT_FOR_PROFIT' or o['status'] == 'PROFIT_ORDER_CANCELED']

        if wait_orders:
            self._handle_orders_wait_for_profit(wait_orders, user_trades)
        self._make_reserve()

    def _handle_open_orders(self, open_orders, user_trades):

        try:
            market_open_orders = [str(order['order_id']) for order in
                                  self._api.get_open_orders(self._currency_1, self._currency_2)]
            for order in open_orders:
                self._handle_open_order(market_open_orders, order, user_trades)
        except Exception as e:
            logger.exception('Cannot handle open orders')

    def _handle_open_order(self, market_open_orders, order, user_trades):
        try:
            if str(order['order_id']) in market_open_orders:
                # order still open
                if order['order_type'] == 'RESERVE':
                    # open profit orders can be ignored
                    self._handle_open_reserve_order(order, user_trades)
            else:
                if not self._is_order_in_trades(order, user_trades):
                    logger.error('Something strange happened. Order {} is completed, but not in trades'.format(
                        order['order_id']))
                    return
                # order completed
                self._handle_completed_order(order)
        except Exception as e:
            logger.exception('Cannot handle order: {}'.format(order['order_id']))

    def _is_order_in_trades(self, order, user_trades):
        return order['order_id'] in [str(t['order_id']) for t in user_trades.get_value()]

    def _handle_completed_order(self, order):
        if order['order_type'] == 'PROFIT':
            # just update status in storage
            self._handle_completed_profit_order(order)
        else:
            self._handle_completed_reserve_order(order)

    def _handle_completed_profit_order(self, order):
        logger.info('Profit order {} completed. Profit: {}, Profile: {}'.format(order['order_id'],
                                                                                order['profit_markup'],
                                                                                order['profile']))
        self._storage.delete(order['order_id'], 'COMPLETED', self._get_time())
        self._storage.delete(order['base_order']['order_id'], 'COMPLETED', self._get_time())
        self._add_profit_to_period(order)

    def _handle_completed_reserve_order(self, order):
        logger.info('Reserve order {} completed'.format(order['order_id']))
        self._storage.update_order_status(order['order_id'], 'WAIT_FOR_PROFIT', self._get_time())
        order['status'] = 'WAIT_FOR_PROFIT'

        self._create_profit_order(order)

    def _handle_open_reserve_order(self, order, user_trades):
        profile, profit_markup, reserve_markup, mean_price = self._advisor.get_advice()
        if order['profile'] == profile:
            my_need_price = self._calculate_desired_reserve_price(mean_price, profile, reserve_markup)
            if math.fabs(my_need_price - float(order['price'])) > float(
                    order['price']) * self._reserve_price_avg_price_deviation:
                logger.debug('Reserve price has changed for order {} -> {}: {}'
                             .format(order['order_id'], order['price'], my_need_price))
                is_order_partially_completed = self._is_order_partially_completed(order, user_trades)
                if is_order_partially_completed:
                    logger.debug('Order {} is partially completed'.format(order['order_id']))
                else:
                    self._cancel_order(order)

        else:
            #TODO id it required?
            logger.debug('Profile has changed for order {}: {} -> {}'
                         .format(order['order_id'], order['profile'], profile))
            if profit_markup < self._profit_markup:
                logger.debug("Profit to small, won't cancel order {}".format(order['order_id']))
            else:
                self._cancel_order(order)

    def _is_order_partially_completed(self, order, user_trades):
        return order['order_id'] in [str(t['order_id']) for t in
                                     user_trades.get_value()]

    def _handle_orders_wait_for_profit(self, wait_orders, user_trades):
        try:
            for order in wait_orders:
                self._handle_order_wait_for_profit(order, user_trades)
        except Exception as e:
            logger.exception('Cannot handle orders waiting for profit')

    def _handle_order_wait_for_profit(self, order, user_trades):
        try:
            profit_orders = [o for o in self._storage.get_open_orders() if o['order_type'] == 'PROFIT'
                             and o['base_order']['order_id'] == order['order_id']]
            if not profit_orders:
                self._create_profit_order(order)

            else:
                for profit_order in profit_orders:
                    self._recalculate_profit_order_price(profit_order, user_trades)
        except Exception as e:
            logger.exception('Cannot handle order waiting for profit {}'.format(order['order_id']))

    def _cancel_order(self, order):
        logger.info('Cancel order {}'.format(order['order_id']))
        self._api.cancel_order(order['order_id'])
        self._storage.delete(order['order_id'], 'CANCELED', self._get_time())

    def _make_reserve(self):
        try:
            profile, profit_markup, reserve_markup, avg_price = self._advisor.get_advice()
            all_orders = self._storage.get_open_orders()
            same_profile_orders = [o for o in all_orders if o['profile'] == profile and o['order_type'] == 'RESERVE'
                                   # or o['status'] == 'WAIT_FOR_PROFIT' and not o['order_id']
                                   #                                           in [oo[
                                   #                                                  'base_order'] if 'base_order' in oo else None
                                   #                                             for oo in all_orders]
                                   ]
            if len(same_profile_orders) >= self._get_max_open_profit_orders_limit(profile):
                logger.debug('Too much orders for profile {}: {}'.format(profile, len(same_profile_orders)))
                return
            if profit_markup < self._profit_markup:
                logger.debug('Too small profit markup: {:.4f} < {}'.format(profit_markup, self._profit_markup))
                return
            # Ордер с минимальным отклонением от текущей средней цены
            if same_profile_orders:
                # TODO check
                min_price_diff = min(
                    [abs(float(
                        o['price'] if o['order_type'] == 'RESERVE' else o['base_order'][
                            'price']) - avg_price) for o in same_profile_orders]) / avg_price
                # Првоеряем минимальное отклонение цены от существующих ордеров:
                if min_price_diff <= self._same_profile_order_price_deviation:
                    logger.debug('Price deviation with other orders is too small: {} < {}'.format(min_price_diff,
                                                                                                  self._same_profile_order_price_deviation))
                    return
            self._create_reserve_order(profile, avg_price, reserve_markup)
        except Exception as e:
            logger.exception('Cannot make reserve')

    def _create_reserve_order(self, profile, avg_price, reserve_markup):
        my_need_price = self._calculate_desired_reserve_price(avg_price, profile, reserve_markup)
        my_amount = self._calculate_desired_reserve_amount(profile)
        new_order_id = str(self._api.create_order(
            currency_1=self._currency_1,
            currency_2=self._currency_2,
            quantity=my_amount,
            price=my_need_price,
            type=self._reserve_order_type(profile)
        ))
        open_orders = self._get_open_orders_for_create()
        new_orders = [order for order in open_orders if str(order['order_id']) == new_order_id]
        if not new_orders:
            # Order already completed
            # Fixme what to do in this case?
            time.sleep(1)
            new_orders = [order for order in open_orders if str(order['order_id']) == new_order_id]
            if not new_orders:
                user_trades = self._get_user_trades()
                new_orders = [order for order in user_trades if str(order['order_id']) == new_order_id]
        if not new_orders:
            # TODO fix
            raise ApiError('Order not found: {}'.format(new_order_id))
        new_order = new_orders[0]
        new_order['quantity'] = str(my_amount)
        new_order['price'] = str(my_need_price)
        stored_order = self._storage.create_order(new_order, profile, 'RESERVE', base_order=None,
                                                  created=self._get_time())
        logger.info('Created new reserve order:\n{}'.format(stored_order))

    def _get_user_trades(self):
        try:
            return self._api.get_user_trades(self._currency_1, self._currency_2)
        except Exception as e:
            # assume api calls limit exceeded
            logger.exception('Cannot read last created order id in trades', e)
            time.sleep(1)
            return self._api.get_user_trades(self._currency_1, self._currency_2)

    def _create_profit_order(self, base_order):
        """
                        Высчитываем курс для продажи.
                        Нам надо продать всю валюту, которую купили, на сумму, за которую купили + немного навара и минус комиссия биржи
                        При этом важный момент, что валюты у нас меньше, чем купили - бирже ушла комиссия
                        0.00134345 1.5045
                    """
        # balances = self._api.get_balances()
        profile, profit_markup, reserve_markup, avg_price = self._advisor.get_advice()
        base_status = base_order['status']
        base_profile = base_order['profile']
        # if profile != base_profile:
        #     logger.debug('Profile has changed: {}->{}. Will not create profit order for reserve order {}'
        #                  .format(base_profile, profile, base_order['order_id']))
        #     return
        # if profit_markup < self._profit_markup:
        #     logger.debug('Profit markup too small: {:.4f} < {}. Will not create profit order for reserve order {}'
        #                  .format(profit_markup, self._profit_markup, base_order['order_id']))

        if base_status == 'WAIT_FOR_PROFIT':
            order_profit_markup = max(profit_markup,
                                      self._profit_markup)
        else:
            order_profit_markup = self._profit_markup
        quantity = self._calculate_profit_quantity(base_order, base_profile, order_profit_markup)

        price = self._calculate_profit_price(quantity, base_order, base_profile, order_profit_markup)
        logger.info('Create new profit order for base order: {}'.format(base_order['order_id']))
        new_order_id = str(self._api.create_order(
            currency_1=self._currency_1,
            currency_2=self._currency_2,
            quantity=quantity,
            price=price,
            type=self._profit_order_type(base_profile),
        ))
        open_orders = self._get_open_orders_for_create()
        new_orders = [order for order in open_orders if str(order['order_id']) == new_order_id]
        if not new_orders:
            # Order already completed
            # Fixme what to do in this case?
            time.sleep(1)
            new_orders = [order for order in open_orders if str(order['order_id']) == new_order_id]
            if not new_orders:
                user_trades = self._get_user_trades()
                new_orders = [order for order in user_trades if str(order['order_id']) == new_order_id]
        if not new_orders:
            raise ApiError('Order not found: {}'.format(new_order_id))
        new_order = new_orders[0]
        new_order['quantity'] = str(quantity)
        new_order['price'] = str(price)

        stored_order = self._storage.create_order(new_order, base_profile, 'PROFIT', base_order=base_order,
                                                  created=self._get_time(), profit_markup=order_profit_markup)
        # self._storage.update_order_status(base_order['order_id'], 'PROFIT_ORDER_CREATED', self._get_time())
        logger.info('Created new profit order: {}'.format(stored_order))

    def _get_open_orders_for_create(self):
        try:
            return self._api.get_open_orders(self._currency_1, self._currency_2)
        except Exception as e:
            # assume api calls limit exceeded
            logger.exception('Cannot read last created order id', e)
            time.sleep(1)
            return self._api.get_open_orders(self._currency_1, self._currency_2)

    def _get_time(self):
        return int(time.time())

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
            if self._profit_currency_up == self._currency_1:
                return self._current_deal_size / ((1 - self._profit_markup) * (1 - self._stock_fee))
            elif self._profit_currency_up == self._currency_2:
                return self._current_deal_size / (1 - self._stock_fee)
            else:
                raise ValueError('Profit currency {} not supported'.format(self._profit_currency_up))
        elif profile == 'DOWN':
            if self._profit_currency_down == self._currency_1:
                return self._current_deal_size
            elif self._profit_currency_down == self._currency_2:
                return self._current_deal_size / (1 - self._profit_markup)
            else:
                raise ValueError('Profit currency {} not supported'.format(self._profit_currency_down))
        raise ValueError('Unrecognized profile: ' + profile)

    def _calculate_desired_reserve_price(self, avg_price, profile, reserve_markup):
        if profile == 'UP':
            # хотим купить подешевле
            return avg_price * (1 + reserve_markup)
        if profile == 'DOWN':
            # хотим продать подороже
            return avg_price * (1 + reserve_markup)
        raise ValueError('Unrecognized profile: ' + profile)

    def _calculate_profit_quantity(self, base_order, profile, profit_markup):
        amount_in_order = float(base_order['quantity'])
        if profile == 'UP':
            if self._profit_currency_up == self._currency_1:
                # Учитываем комиссию
                return max(self._currency_1_deal_size,
                           amount_in_order * (1 - self._stock_fee) * (1 - self._profit_markup))
            elif self._profit_currency_up == self._currency_2:
                return max(self._currency_1_deal_size, amount_in_order * (1 - self._stock_fee))
            else:
                raise ValueError('Profit currency {} not supported'.format(self._profit_currency_up))
        elif profile == 'DOWN':
            if self._profit_currency_down == self._currency_1:
                return max(self._currency_1_deal_size, amount_in_order * (1 + profit_markup)) / (1 - self._stock_fee)
            elif self._profit_currency_down == self._currency_2:
                return max(self._currency_1_deal_size, amount_in_order / (1 - self._stock_fee))
            else:
                raise ValueError('Profit currency {} not supported'.format(self._profit_currency_down))

            # Комиссия была в долларах
        raise ValueError('Unrecognized profile: ' + profile)

    def _calculate_profit_price(self, quantity, base_order, profile, profit_markup):
        price_in_order = float(base_order['price'])
        amount_in_order = float(base_order['quantity'])
        if profile == 'UP':
            if self._profit_currency_up == self._currency_1:
                # Комиссия была снята в 1 валюте, считаем от цены ордера
                return amount_in_order * price_in_order / quantity * (1 - self._stock_fee)
            elif self._profit_currency_up == self._currency_2:
                return amount_in_order * price_in_order * (1 + profit_markup) / (quantity * (1 - self._stock_fee))
            else:
                raise ValueError('Profit currency {} not supported'.format(self._profit_currency_up))
        if profile == 'DOWN':
            if self._profit_currency_down == self._currency_1:
                return (amount_in_order * price_in_order * (1 - self._stock_fee)) / quantity
            elif self._profit_currency_down == self._currency_2:
                return (amount_in_order * price_in_order * (1 - self._stock_fee) * (1 - profit_markup)) / quantity
            else:
                raise ValueError('Profit currency {} not supported'.format(self._profit_currency_down))
        raise ValueError('Unrecognized profile: ' + profile)

    def _get_max_open_profit_orders_limit(self, profile):
        if profile == 'UP':
            return self._max_profit_orders_up
        if profile == 'DOWN':
            return self._max_profit_orders_down
        raise ValueError('Invalid profile: ' + profile)

    def _recalculate_profit_order_price(self, profit_order, ser_trades):
        profile, profit_markup, reserve_markup, avg_price = self._advisor.get_advice()
        if int(self._get_time() - profit_order['created']) > self._profit_order_lifetime \
                and float(profit_order['profit_markup']) != self._profit_markup:
            if profit_order['profile'] == 'DOWN':
                desired_profit_amount = self._calculate_profit_quantity(profit_order['base_order'],
                                                                        profit_order['profile'],
                                                                        self._profit_markup)
            else:
                desired_profit_amount = float(profit_order['quantity'])
            desired_profit_price = self._calculate_profit_price(desired_profit_amount,
                                                                profit_order['base_order'],
                                                                profit_order['profile'],
                                                                self._profit_markup)
            if abs(desired_profit_price - float(profit_order[
                                                    'price'])) / desired_profit_price > self._profit_price_prev_price_deviation \
                    and abs(
                                desired_profit_price - avg_price) / desired_profit_price > self._profit_price_avg_price_deviation:
                logger.debug('Profit markup has changed for order {}'.format(profit_order['order_id']))
                self._cancel_order(profit_order)
                self._storage.update_order_status(profit_order['base_order']['order_id'], 'PROFIT_ORDER_CANCELED',
                                                  self._get_time())

    def _create_period(self, start_time, target_profit):
        end = start_time + timedelta(hours=self._target_period).total_seconds()
        logger.info('Create period. End: {}. Target profit: {}'.format(end, target_profit))
        return Period(end, target_profit, self._target_currency)

    def _check_profit(self):

        if self._target_period is None or self._target_profit is None:
            return
        current_period = self._current_period
        if current_period is None:
            # create new period
            self._current_period = self._create_period(self._get_time(), self._target_profit)
        else:
            if current_period.end < self._get_time():
                # period is elapsed
                if current_period.profit >= current_period.target_profit:
                    # profit achieved
                    if self._current_deal_size > self._currency_1_deal_size:
                        logger.info('Profit {} achieved. Change deal size to {}'.format(current_period.target_profit,
                                                                                        self._currency_1_deal_size))
                        self._current_deal_size = self._currency_1_deal_size
                    self._current_period = self._create_period(current_period.end, self._target_profit)
                else:
                    # profit not achieved
                    profit_remainder = current_period.target_profit - current_period.profit
                    target_profit = self._target_profit + profit_remainder
                    factor = target_profit / current_period.target_profit
                    new_deal_size = min(self._current_deal_size * factor, self._currency_1_max_deal_size)
                    logger.info('Profit {} not achieved. Change deal size to {}'.format(
                        current_period.target_profit, new_deal_size))
                    self._current_deal_size = new_deal_size
                    self._current_period = self._create_period(current_period.end, target_profit)

    def _add_profit_to_period(self, order):
        order_profit = Counter()
        profit = 0
        if self._current_period is None:
            return
        if order['type'] == 'buy':
            order_profit[self._currency_1] += float(order['quantity']) * (1 - self._stock_fee)
            order_profit[self._currency_2] -= float(order['price']) * float(order['quantity'])
            order_profit[self._currency_1] -= float(order['base_order']['quantity'])
            order_profit[self._currency_2] += float(order['base_order']['price']) * float(
                order['base_order']['quantity']) * (1 - self._stock_fee)
        else:
            order_profit[self._currency_1] -= float(order['quantity'])
            order_profit[self._currency_2] += float(order['price']) * float(order['quantity']) * (1 - self._stock_fee)
            order_profit[self._currency_1] += float(order['base_order']['quantity']) * (1 - self._stock_fee)
            order_profit[self._currency_2] -= float(order['base_order']['price']) * float(
                order['base_order']['quantity'])

        for cur, pr in order_profit.items():
            if cur == self._target_currency:
                profit += pr
            else:
                if self._target_currency == self._currency_2:
                    profit += pr * float(order['price'])
                else:
                    profit += pr / float(order['price'])
        self._current_period.profit += profit
        if self._current_period.profit >= self._current_period.target_profit and self._current_deal_size > self._currency_1_deal_size:
            logger.info('Profit {} achieved. Change deal size to {}'.format(self._current_period.target_profit,
                                                                            self._currency_1_deal_size))

            self._current_deal_size = self._currency_1_deal_size


class Period:
    def __init__(self, end, target_profit, target_currency):
        self.end = end
        self.target_profit = target_profit
        self.target_currency = target_currency
        self.profit = 0
