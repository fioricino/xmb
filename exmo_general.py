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

        if 'currency_1_min_deal_size' in kwargs:
            self._currency_1_min_deal_size = kwargs['currency_1_min_deal_size']
        else:
            self._currency_1_min_deal_size = 0.001

        if 'trend_min_deal_size' in kwargs:
            self._trend_min_deal_size = kwargs['trend_min_deal_size']
        else:
            self._trend_min_deal_size = 0.001

        if 'max_profit_orders_up' in kwargs:
            self._max_profit_orders_up = kwargs['max_profit_orders_up']
        else:
            self._max_profit_orders_up = 100

        if 'max_profit_orders_down' in kwargs:
            self._max_profit_orders_down = kwargs['max_profit_orders_down']
        else:
            self._max_profit_orders_down = 100

        if 'same_profile_order_price_deviation' in kwargs:
            self._same_profile_order_price_deviation = kwargs['same_profile_order_price_deviation']
        else:
            self._same_profile_order_price_deviation = 0.02

        if 'same_profile_order_same_direction_price_deviation' in kwargs:
            self._same_profile_order_same_direction_price_deviation = kwargs[
                'same_profile_order_same_direction_price_deviation']
        else:
            self._same_profile_order_same_direction_price_deviation = 0.02

        if 'profit_currency_up' in kwargs:
            self._profit_currency_up = kwargs['profit_currency_up']
        else:
            self._profit_currency_up = self._currency_2

        if 'profit_currency_down' in kwargs:
            self._profit_currency_down = kwargs['profit_currency_down']
        else:
            self._profit_currency_down = self._currency_1

        if 'suspend_price_deviation' in kwargs:
            self._suspend_deviation = kwargs['suspend_price_deviation']
        else:
            self._suspend_deviation = None

        if 'suspend_price_up_down_deviation' in kwargs:
            self._suspend_price_up_down_deviation = kwargs['suspend_price_up_down_deviation']
        else:
            self._suspend_price_up_down_deviation = 0.05


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
        profile, profit_markup, mean_price, deal_size = self._advisor.get_advice()
        profile = order['profile']
        deal_size = self._trend_min_deal_size
        # if order['profile'] == profile:
        my_need_price = self._calculate_desired_reserve_price(mean_price, profile, 0)
        if math.fabs(my_need_price - float(order['price'])) > float(
                order['price']) * self._reserve_price_avg_price_deviation:
            logger.debug('Reserve price has changed for order {} -> {}: {}'
                         .format(order['order_id'], order['price'], my_need_price))
            is_order_partially_completed = self._is_order_partially_completed(order, user_trades)
            if is_order_partially_completed:
                logger.debug('Order {} is partially completed'.format(order['order_id']))
            else:
                self._cancel_order(order)

                # else:
                #     #TODO id it required?
                #     logger.debug('Profile has changed for order {}: {} -> {}'
                #                  .format(order['order_id'], order['profile'], profile))
                #     if profit_markup < self._profit_markup:
                #         logger.debug("Profit to small, won't cancel order {}".format(order['order_id']))
                #     else:
                #         self._cancel_order(order)

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
            profile, profit_markup, avg_price, deal_size = self._advisor.get_advice()
            profile = order['profile']
            deal_size = self._trend_min_deal_size
            price = float(order['price'])
            if not profit_orders:
                if self._suspend_deviation is None \
                        or order['profile'] == 'UP' and (
                            price - avg_price) / price <= self._suspend_deviation - \
                                self._suspend_price_up_down_deviation \
                        or order['profile'] == 'DOWN' and (
                            avg_price - price) / price <= self._suspend_deviation - self._suspend_price_up_down_deviation:
                    self._create_profit_order(order)
            else:
                if self._suspend_deviation is not None \
                        and (order['profile'] == 'UP' and (
                            price - avg_price) / price >= self._suspend_deviation +
                            self._suspend_price_up_down_deviation \
                                     or order['profile'] == 'DOWN' and (
                                avg_price - price) / price >= self._suspend_deviation + self._suspend_price_up_down_deviation):
                    for profit_order in profit_orders:
                        self._cancel_order(profit_order)
        except Exception as e:
            logger.exception('Cannot handle order waiting for profit {}'.format(order['order_id']))

    def _cancel_order(self, order):
        logger.info('Cancel order {}'.format(order['order_id']))
        self._api.cancel_order(order['order_id'])
        self._storage.delete(order['order_id'], 'CANCELED', self._get_time())

    def _make_reserve(self):
        try:
            profile, profit_markup, avg_price, deal_size = self._advisor.get_advice()
            all_orders = self._storage.get_open_orders()
            for profile in ['UP', 'DOWN']:
                self._make_reserve_profile(profile, avg_price, self._trend_min_deal_size, self._profit_markup,
                                           all_orders)
        except Exception as e:
            logger.exception('Cannot make reserve')

    def _make_reserve_profile(self, profile, avg_price, deal_size, profit_markup, all_orders):
        same_profile_orders = [o for o in all_orders if o['profile'] == profile and o['order_type'] == 'RESERVE'
                               # or o['status'] == 'WAIT_FOR_PROFIT' and not o['order_id']
                               #                                           in [oo[
                               #                                                  'base_order'] if 'base_order' in oo
                               #  else None
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
            smaller_orders = [o for o in same_profile_orders if float(o['price']) <= avg_price]
            bigger_orders = [o for o in same_profile_orders if float(o['price']) >= avg_price]
            if profile == 'UP':
                same_dir_orders = bigger_orders
                other_dir_orders = smaller_orders
            elif profile == 'DOWN':
                same_dir_orders = smaller_orders
                other_dir_orders = bigger_orders
            else:
                raise ValueError('Invalid profile: {}'.format(profile))
            # TODO check
            if other_dir_orders:
                min_price_diff = min(
                    [abs(float(
                        o['price'] if o['order_type'] == 'RESERVE' else o['base_order'][
                            'price']) - avg_price) for o in other_dir_orders]) / avg_price
                # Првоеряем минимальное отклонение цены от существующих ордеров:
                if min_price_diff <= self._same_profile_order_price_deviation:
                    logger.debug('Price deviation with other orders is too small: {} < {}'.format(min_price_diff,
                                                                                                  self._same_profile_order_price_deviation))
                    return
            if same_dir_orders:
                min_price_diff = min(
                    [abs(float(
                        o['price'] if o['order_type'] == 'RESERVE' else o['base_order'][
                            'price']) - avg_price) for o in same_dir_orders]) / avg_price
                # Првоеряем минимальное отклонение цены от существующих ордеров:
                if min_price_diff <= self._same_profile_order_same_direction_price_deviation:
                    logger.debug('Price deviation with other orders is too small: {} < {}'.format(min_price_diff,
                                                                                                  self._same_profile_order_price_deviation))
                    return
        self._create_reserve_order(profile, avg_price, 0, deal_size)

    def _create_reserve_order(self, profile, avg_price, reserve_markup, deal_size):
        my_need_price = self._calculate_desired_reserve_price(avg_price, profile, reserve_markup)
        my_amount = self._calculate_desired_reserve_amount(profile, avg_price, deal_size)
        if my_amount is None:
            logger.debug('Deal size too small')
            return

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
            open_orders = self._get_open_orders_for_create()
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
        # profile, profit_markup, reserve_markup, avg_price = self._advisor.get_advice()
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
            order_profit_markup = self._profit_markup
        else:
            order_profit_markup = self._profit_markup
        quantity = self._calculate_profit_quantity(float(base_order['quantity']), base_profile, order_profit_markup)
        price = self._calculate_profit_price(quantity, float(base_order['quantity']), float(base_order['price']),
                                             base_profile, order_profit_markup)
        order_type = self._profit_order_type(base_profile)
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
            open_orders = self._get_open_orders_for_create()
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

    def _calculate_desired_reserve_amount(self, profile, price, deal_size):
        if deal_size < self._trend_min_deal_size:
            return None
        if profile == 'UP':
            if self._profit_currency_up == self._currency_1:
                return max(self._currency_1_min_deal_size,
                           deal_size / (
                               (1 - self._profit_markup) * (1 - self._stock_fee)))
            elif self._profit_currency_up == self._currency_2:
                return max(self._currency_1_min_deal_size,
                           deal_size / (1 - self._stock_fee))
            else:
                raise ValueError('Profit currency {} not supported'.format(self._profit_currency_up))
        elif profile == 'DOWN':
            if self._profit_currency_down == self._currency_1:
                return max(self._currency_1_min_deal_size, deal_size)
            elif self._profit_currency_down == self._currency_2:
                return max(self._currency_1_min_deal_size,
                           deal_size / (1 - self._profit_markup))
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

    def _get_max_open_profit_orders_limit(self, profile):
        if profile == 'UP':
            return self._max_profit_orders_up
        if profile == 'DOWN':
            return self._max_profit_orders_down
        raise ValueError('Invalid profile: ' + profile)

    def _recalculate_profit_order_price(self, profit_order, ser_trades):
        return
        profile, profit_markup, reserve_markup, avg_price = self._advisor.get_advice()
        if int(self._get_time() - profit_order['created']) > self._profit_order_lifetime \
                and float(profit_order['profit_markup']) != self._profit_markup:
            if profit_order['profile'] == 'DOWN':
                desired_profit_amount = self._calculate_profit_quantity(float(profit_order['base_order']['quantity']),
                                                                        profit_order['profile'],
                                                                        self._profit_markup)
            else:
                desired_profit_amount = float(profit_order['quantity'])
            desired_profit_price = self._calculate_profit_price(desired_profit_amount,
                                                                float(profit_order['base_order']['quantity']),
                                                                float(profit_order['base_order']['price']),
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


