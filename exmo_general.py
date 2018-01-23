import logging
import math
import time
from enum import Enum

from exceptions import ApiError


class Profiles(Enum):
    UP = 1
    DOWN = 2


class Worker:
    def __init__(self, api,
                 storage,
                 profile,
                 period=1,
                 currency_1='BTC',
                 currency_2='USD',
                 order_life_time=60,
                 avg_price_period=900,
                 stock_fee=0.002,
                 profit_markup=0.001,
                 reserve_price_distribution=0.001,
                 currency_1_deal_size=0.001,
                 stock_time_offset=0
                 ):
        self._api = api
        self._storage = storage
        self._period = period
        self._interrupted = False
        self._currency_1 = currency_1
        self._currency_2 = currency_2
        self._profile = profile
        self._stock_time_offset = stock_time_offset
        self._order_life_time = order_life_time
        self._avg_price_period = avg_price_period
        self._stock_fee = stock_fee
        self._profit_markup = profit_markup
        self._reserve_price_distribution = reserve_price_distribution
        self._currency_1_deal_size = currency_1_deal_size
        # self._currency_2_deal_size = currency_2_deal_size

    def run(self):
        self._interrupted = False
        # Синхронизируем базу с биржей
        while not self._interrupted:
            try:
                self.main_flow()
                time.sleep(self._period)
            except ApiError as e:
                logging.error(str(e))
            except self.ScriptQuitCondition as e:
                logging.debug(str(e))
                pass
            except Exception as e:
                logging.fatal(str(e))

    def stop(self):
        self._interrupted = True

    class ScriptQuitCondition(Exception):
        pass

    def main_flow(self):
        # Получаем список активных ордеров
        opened_orders = [order for order in self._storage.get_open_orders() if order['profile'] == self._profile.name]
        market_open_orders = [order['order_id'] for order in
                              self._api.get_open_orders(self._currency_1, self._currency_2)]

        reserve_orders = []
        # Есть ли неисполненные ордера на доход (продажа CURRENCY_1 для повышения, покупка CURRENCY_1 для понижения)?
        for order in opened_orders:
            if order['order_type'] == 'PROFIT':
                # Есть неисполненные ордера на доход, выход
                # Ордер еще не закрыт?
                if order['order_data']['order_id'] in market_open_orders:
                    raise self.ScriptQuitCondition(
                        'Выход, ждем пока не закроется ордер на доход {}:'.format(order['order_data']['order_id']))
                else:
                    # Ордер выполнен, обновляем хранилище
                    self._storage.delete(order['order_data']['order_id'], 'COMPLETED')
                    self._storage.delete(order['base_order']['order_id'], 'COMPLETED')
                    raise self.ScriptQuitCondition(
                        'Выход, закрыли ордера на доход'.format(order['order_data']['order_id']))
            if order['status'] == 'OPEN':
                # Запоминаем ордера на запас
                reserve_orders.append(order)

        # Проверяем, есть ли открытые ордера на запас (покупку CURRENCY_1 для повышения, продажа для понижения)
        if reserve_orders:  # открытые ордера есть
            for order_data in reserve_orders:
                order = order_data['order_data']
                # Проверяем, есть ли частично исполненные
                logging.debug('Проверяем, что происходит с ордером на резерв %s', str(order['order_id']))
                # Ордер еще открыт?
                if order['order_id'] in market_open_orders:
                    is_order_partially_completed = self._api.is_order_partially_completed(order['order_id'])
                    if is_order_partially_completed:
                        # по ордеру уже есть частичное выполнение, выход
                        raise self.ScriptQuitCondition(
                            'Выход, продолжаем надеяться запасти валюту по тому курсу, по которому уже запасли часть')
                    else:
                        logging.debug('Частично исполненных ордеров нет')

                        self.check_reserve_order(order)
                else:
                    # Ордер выполнен, обновляем хранилище
                    self._storage.update_order_status(order['order_id'], 'WAIT_FOR_PROFIT')

        else:  # Открытых ордеров нет
            # Есть ли ожидающие ордера на резерв?
            orders_waiting_for_profit = [order['order_data'] for order in opened_orders
                                         if order['status'] == 'WAIT_FOR_PROFIT']
            if orders_waiting_for_profit:
                # if self.check_balance_for_profit_order(balances):  # Есть ли в наличии CURRENCY_1, которую можно продать?
                for order in orders_waiting_for_profit:
                    self.create_profit_order(order)
            else:
                # CURRENCY_1 нет, надо докупить
                # Достаточно ли денег на балансе в валюте CURRENCY_2 (Баланс >= CAN_SPEND)
                # if self.check_balance_for_reserve_order(balances):
                self.create_reserve_order()
                # else:
                #     raise self.ScriptQuitCondition('Выход, не хватает денег')

    def check_reserve_order(self, order):
        time_passed = time.time() + self._stock_time_offset * 60 * 60 - int(order['created'])
        if time_passed > self._order_life_time:
            my_need_price = self.get_desired_reserve_price()
            if math.fabs(my_need_price - float(order['price'])) > float(
                    order['price']) * self._reserve_price_distribution:
                # Ордер уже давно висит, никому не нужен, отменяем
                self._api.cancel_order(order['order_id'])
                self._storage.delete(order['order_id'], 'CANCELED')
                raise self.ScriptQuitCondition(
                    'Отменяем ордер -за ' + str(time_passed) + ' секунд не удалось зарезервировать ')
            else:
                raise self.ScriptQuitCondition(
                    'Не отменяем ордер, так как курс не изменился за {} секунд: {}.'.format(time_passed,
                                                                                            my_need_price))
        else:
            raise self.ScriptQuitCondition(
                'Выход, продолжаем надеяться зарезервировать валюту по указанному ранее курсу, со времени создания ордера прошло %s секунд' % str(
                    time_passed))

    def create_reserve_order(self):
        my_need_price = self.get_desired_reserve_price()
        my_amount = self.calculate_desired_reserve_amount()
        logging.info('%s %s %s', self.profit_order_type(), str(my_amount), str(my_need_price))
        new_order_id = self._api.create_order(
            currency_1=self._currency_1,
            currency_2=self._currency_2,
            quantity=my_amount,
            price=my_need_price,
            type=self.reserve_order_type()
        )
        open_orders = self._api.get_open_orders(self._currency_1, self._currency_2)
        new_order = next(order for order in open_orders if order['order_id'] == new_order_id)
        self._storage.create_order(new_order, self._profile, 'RESERVE')
        logging.info(str(new_order))
        logging.debug('Создан ордер на покупку %s', str(new_order['order_id']))

    def create_profit_order(self, base_order):
        """
                        Высчитываем курс для продажи.
                        Нам надо продать всю валюту, которую купили, на сумму, за которую купили + немного навара и минус комиссия биржи
                        При этом важный момент, что валюты у нас меньше, чем купили - бирже ушла комиссия
                        0.00134345 1.5045
                    """
        # balances = self._api.get_balances()
        quantity = self.calculate_profit_quantity(base_order)

        price = self.calculate_profit_price(quantity, base_order)
        logging.info('%s %s for %s', str(self.profit_order_type()), str(quantity), str(price),
                     str(price))
        new_order_id = self._api.create_order(
            currency_1=self._currency_1,
            currency_2=self._currency_2,
            quantity=quantity,
            price=price,
            type=self.profit_order_type()
        )
        open_orders = self._api.get_open_orders(self._currency_1, self._currency_2)
        new_order = next(order for order in open_orders if order['order_id'] == new_order_id)
        self._storage.create_order(new_order, self._profile, 'PROFIT', base_order)
        self._storage.update_order_status(base_order['order_id'], 'PROFIT_ORDER_CREATED')
        logging.info(str(new_order))
        logging.debug('Создан ордер на доход %s', str(new_order['order_id']))

    def check_balance_for_reserve_order(self, balances):
        if self._profile == Profiles.UP:
            return float(balances[self._currency_2]) >= self._currency_2_deal_size
        elif self._profile == Profiles.DOWN:
            return float(balances[self._currency_1]) >= self._currency_1_deal_size
        raise ValueError

    def check_balance_for_profit_order(self, balances):
        if self._profile == Profiles.UP:
            return float(balances[self._currency_1]) >= self._currency_1_deal_size
        elif self._profile == Profiles.DOWN:
            return float(balances[self._currency_2]) >= self._currency_2_deal_size
        raise ValueError

    def profit_order_type(self):
        if self._profile == Profiles.UP:
            return 'sell'
        elif self._profile == Profiles.DOWN:
            return 'buy'
        raise ValueError('Unrecognized profile: ' + self._profile)

    def reserve_order_type(self):
        if self._profile == Profiles.UP:
            return 'buy'
        elif self._profile == Profiles.DOWN:
            return 'sell'
        raise ValueError('Unrecognized profile: ' + self._profile)

    def get_desired_reserve_price(self):
        """
                                Посчитать, сколько валюты CURRENCY_1 можно купить.
                                На сумму CAN_SPEND за минусом STOCK_FEE, и с учетом PROFIT_MARKUP
                                ( = ниже средней цены рынка, с учетом комиссии и желаемого профита)
                            """
        # написать для прнижения!!!
        avg_price = self.get_avg_price()
        # купить/продать больше, потому что биржа потом заберет кусок
        my_need_price = self.calculate_desired_reserve_price(avg_price)
        # туду вынести наружу
        return my_need_price

    def calculate_desired_reserve_amount(self):
        if self._profile == Profiles.UP:
            return self._currency_1_deal_size / (1 - self._stock_fee)
        elif self._profile == Profiles.DOWN:
            return self._currency_1_deal_size

    def calculate_desired_reserve_price(self, avg_price):
        if self._profile == Profiles.UP:
            # хотим купить подешевле
            return avg_price / (1 + self._stock_fee)
        if self._profile == Profiles.DOWN:
            # хотим продать подороже
            return avg_price / (1 - self._stock_fee)

    def get_avg_price(self):
        # Узнать среднюю цену за AVG_PRICE_PERIOD, по которой продают CURRENCY_1
        """
                                     Exmo не предоставляет такого метода в API, но предоставляет другие, к которым можно попробовать привязаться.
                                     У них есть метод required_total, который позволяет подсчитать курс, но,
                                         во-первых, похоже он берет текущую рыночную цену (а мне нужна в динамике), а
                                         во-вторых алгоритм расчета скрыт и может измениться в любой момент.
                                     Сейчас я вижу два пути - либо смотреть текущие открытые ордера, либо последние совершенные сделки.
                                     Оба варианта мне не слишком нравятся, но завершенные сделки покажут реальные цены по которым продавали/покупали,
                                     а открытые ордера покажут цены, по которым только собираются продать/купить - т.е. завышенные и заниженные.
                                     Так что берем информацию из завершенных сделок.
                                    """
        deals = self._api.get_trades(currency_1=self._currency_1, currency_2=self._currency_2)
        # prices = []
        amount = 0
        quantity = 0
        for deal in deals:
            time_passed = time.time() + self._stock_time_offset * 60 * 60 - int(deal['date'])
            if time_passed < self._avg_price_period:
                # prices.append(float(deal['price']))
                amount += float(deal['amount'])
                quantity += float(deal['quantity'])
                if quantity == 0:
                    raise self.ScriptQuitCondition('Не удается вычислить среднюю цену')
        avg_price = amount / quantity
        return avg_price

    def calculate_profit_quantity(self, base_order):
        amount_in_order = float(base_order['quantity'])
        if self._profile == Profiles.UP:
            # Учитываем комиссию
            return amount_in_order * (1 - self._stock_fee)
        elif self._profile == Profiles.DOWN:
            # Комиссия была в долларах
            return amount_in_order * (1 + self._profit_markup) / (1 - self._stock_fee)
        raise ValueError

    def calculate_profit_price(self, quantity, base_order):
        price_in_order = float(base_order['price'])
        amount_in_order = float(base_order['quantity'])
        if self._profile == Profiles.UP:
            # Комиссия была снята в 1 валюте, считаем от цены ордера
            return (
                amount_in_order * price_in_order * (1 + self._profit_markup) / ((1 - self._stock_fee) * quantity))
        if self._profile == Profiles.DOWN:
            return (amount_in_order * price_in_order * (1 - self._stock_fee)) / quantity
        raise ValueError
