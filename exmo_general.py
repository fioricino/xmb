import logging
import math
import time

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
                 profit_advisor,
                 deal_sizer,
                 **kwargs):
        self._api = api
        self._storage = storage
        self._advisor = advisor
        self._deal_sizer = deal_sizer
        self._interrupted = False
        self._profit_advisor = profit_advisor

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

        if 'currency_1_min_deal_size' in kwargs:
            self._currency_1_min_deal_size = kwargs['currency_1_min_deal_size']
        else:
            self._currency_1_min_deal_size = 0.001

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
            self._same_profile_order_price_deviation = 0.05

        if 'profit_currency_up' in kwargs:
            self._profit_currency_up = kwargs['profit_currency_up']
        else:
            self._profit_currency_up = self._currency_2

        if 'profit_currency_down' in kwargs:
            self._profit_currency_down = kwargs['profit_currency_down']
        else:
            self._profit_currency_down = self._currency_1

        if 'currency_1_max_deal_size' in kwargs:
            self._currency_1_max_deal_size = kwargs['currency_1_max_deal_size']
        else:
            self._currency_1_max_deal_size = 0.002

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
        user_trades = Lazy(self._api.get_user_trades, self._currency_1, self._currency_2)

        open_orders = [o for o in self._storage.get_open_orders() if o['status'] == 'OPEN']

        if open_orders:
            self._handle_open_orders(open_orders, user_trades)

        all_orders = self._storage.get_open_orders()
        wait_orders = [o for o in all_orders if
                       o['status'] == 'WAIT_FOR_PROFIT' or o['status'] == 'PROFIT_ORDER_CANCELED']

        if wait_orders:
            self._handle_orders_wait_for_profit(wait_orders, user_trades, all_orders)
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

    def _handle_completed_reserve_order(self, order):
        logger.info('Reserve order {} completed'.format(order['order_id']))
        self._storage.update_order_status(order['order_id'], 'WAIT_FOR_PROFIT', self._get_time())
        order['status'] = 'WAIT_FOR_PROFIT'

        self._create_profit_order(order)

    def _handle_open_reserve_order(self, order, user_trades):
        profile, avg_price, mean_price = self._advisor.get_advice()
        if profile is not None and avg_price is not None and order['profile'] == profile:
            my_need_price = self._calculate_desired_reserve_price(avg_price)
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
            self._cancel_order(order)

    def _is_order_partially_completed(self, order, user_trades):
        return order['order_id'] in [str(t['order_id']) for t in
                                     user_trades.get_value()]

    def _handle_orders_wait_for_profit(self, wait_orders, user_trades, all_orders):
        try:
            for order in wait_orders:
                self._handle_order_wait_for_profit(order, user_trades, all_orders)
        except Exception as e:
            logger.exception('Cannot handle orders waiting for profit')

    def _handle_order_wait_for_profit(self, order, user_trades, all_orders):
        try:
            profit_orders = [o for o in all_orders if o['order_type'] == 'PROFIT'
                             and o['base_order']['order_id'] == order['order_id']]
            if not profit_orders:
                self._create_profit_order(order)

        except Exception as e:
            logger.exception('Cannot handle order waiting for profit {}'.format(order['order_id']))

    def _cancel_order(self, order):
        logger.info('Cancel order {}'.format(order['order_id']))
        self._api.cancel_order(order['order_id'])
        self._storage.delete(order['order_id'], 'CANCELED', self._get_time())

    def _make_reserve(self):
        try:
            profile, avg_price, mean_price = self._advisor.get_advice()
            if profile is None:
                logger.debug('Will not make reserve.')
                return
            all_orders = self._storage.get_open_orders()
            same_profile_orders = [o for o in all_orders if o['profile'] == profile and o['order_type'] == 'RESERVE']
            if len(same_profile_orders) >= self._get_max_open_profit_orders_limit(profile):
                logger.debug('Too much orders for profile {}: {}'.format(profile, len(same_profile_orders)))
                return
            # Ордер с минимальным отклонением от текущей средней цены
            if same_profile_orders:
                # TODO check
                min_price_diff = min(
                    [abs(float(
                        o['mean_price']) - mean_price) for o in same_profile_orders]) / mean_price
                # Првоеряем минимальное отклонение цены от существующих ордеров:
                if min_price_diff <= self._same_profile_order_price_deviation:
                    logger.debug('Price deviation with other orders is too small: {} < {}'.format(min_price_diff,
                                                                                                  self._same_profile_order_price_deviation))
                    return
                if any(o for o in same_profile_orders if profile == 'UP' and mean_price > float(o['mean_price'])
                or profile == 'DOWN' and mean_price < float(o['mean_price'])):
                    logger.debug('There is open order for profile {}'.format(profile))
                    return
            self._create_reserve_order(profile, avg_price, mean_price)
        except Exception as e:
            logger.exception('Cannot make reserve')

    def _create_reserve_order(self, profile, avg_price, mean_price):
        my_need_price = self._calculate_desired_reserve_price(avg_price)
        my_amount = self._calculate_desired_reserve_amount(profile, avg_price)
        order_type = self._reserve_order_type(profile)
        new_order_id = str(self._api.create_order(
            currency_1=self._currency_1,
            currency_2=self._currency_2,
            quantity=my_amount,
            price=my_need_price,
            type=order_type
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
        new_order['mean_price'] = mean_price
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
        price, quantity, order_type = self._profit_advisor.get_profit_order(base_order)
        if price is None or quantity is None or order_type is None:
            logger.debug('Will not create profit order.')
            return

        logger.info('Create new profit order for base order: {}'.format(base_order['order_id']))
        new_order_id = str(self._api.create_order(
            currency_1=self._currency_1,
            currency_2=self._currency_2,
            quantity=quantity,
            price=price,
            type=order_type,
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
        new_order['mean_price'] = base_order['mean_price']

        stored_order = self._storage.create_order(new_order, base_order['profile'], 'PROFIT', base_order=base_order,
                                                  created=self._get_time(), profit_markup=self._profit_markup)
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


    def _reserve_order_type(self, profile):
        if profile == 'UP':
            return 'buy'
        elif profile == 'DOWN':
            return 'sell'
        raise ValueError('Unrecognized profile: ' + profile)

    def _calculate_desired_reserve_amount(self, profile, price):
        if profile == 'UP':
            if self._profit_currency_up == self._currency_1:
                return max(self._currency_1_min_deal_size,
                           self._deal_sizer.get_deal_size(price, profile) / (
                           (1 - self._profit_markup) * (1 - self._stock_fee)))
            elif self._profit_currency_up == self._currency_2:
                return max(self._currency_1_min_deal_size,
                           self._deal_sizer.get_deal_size(price, profile) / (1 - self._stock_fee))
            else:
                raise ValueError('Profit currency {} not supported'.format(self._profit_currency_up))
        elif profile == 'DOWN':
            if self._profit_currency_down == self._currency_1:
                return max(self._currency_1_min_deal_size, self._deal_sizer.get_deal_size(price, profile))
            elif self._profit_currency_down == self._currency_2:
                return max(self._currency_1_min_deal_size,
                           self._deal_sizer.get_deal_size(price, profile) / (1 - self._profit_markup))
            else:
                raise ValueError('Profit currency {} not supported'.format(self._profit_currency_down))
        raise ValueError('Unrecognized profile: ' + profile)

    def _calculate_desired_reserve_price(self, avg_price):
        return avg_price

    def _get_max_open_profit_orders_limit(self, profile):
        if profile == 'UP':
            return self._max_profit_orders_up
        if profile == 'DOWN':
            return self._max_profit_orders_down
        raise ValueError('Invalid profile: ' + profile)


