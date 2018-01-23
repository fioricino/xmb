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
                 profile,
                 period=1,
                 currency_1='BTC',
                 currency_2='USD',
                 order_life_time=60,
                 avg_price_period=900,
                 stock_fee=0.002,
                 spend_profit_markup=0.001,
                 reserve_price_distribution=0.001,
                 currency_1_deal_size=0.001,
                 currency_2_deal_size=15,
                 currency_1_min_deal_size=0.001,
                 stock_time_offset=0
                 ):
        self._api = api
        self._period = period
        self._interrupted = False
        self._currency_1 = currency_1
        self._currency_2 = currency_2
        self._profile = profile
        self._stock_time_offset = stock_time_offset
        self._order_life_time = order_life_time
        self._avg_price_period = avg_price_period
        self._stock_fee = stock_fee
        self._spend_profit_markup = spend_profit_markup
        self._reserve_price_distribution = reserve_price_distribution
        self._currency_1_deal_size = currency_1_deal_size
        self._currency_2_deal_size = currency_2_deal_size
        self._currency_1_min_deal_size = currency_1_min_deal_size

    def run(self):
        self._interrupted = False
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
        opened_orders = self._api.get_open_orders(self._currency_1, self._currency_2)

        reserve_orders = []
        # Есть ли неисполненные ордера на доход (продажа CURRENCY_1 для повышения, покупка CURRENCY_1 для понижения)?
        for order in opened_orders:
            if order['type'] == self.profit_order_type():
                # Есть неисполненные ордера на доход, выход
                raise self.ScriptQuitCondition(
                    'Выход, ждем пока не исполнятся/закроются все ордера типа {} (один ордер может быть разбит биржей на несколько и исполняться частями)'.format(
                        self.profit_order_type()))
            else:
                # Запоминаем ордера на запас
                reserve_orders.append(order)

        # Проверяем, есть ли открытые ордера на запас (покупку CURRENCY_1 для повышения, продажа для понижения)
        if reserve_orders:  # открытые ордера есть
            for order in reserve_orders:
                # Проверяем, есть ли частично исполненные
                logging.debug('Проверяем, что происходит с отложенным ордером %s', str(order['order_id']))
                is_order_partially_completed = self._api.is_order_partially_completed(order['order_id'])
                if is_order_partially_completed:
                    # по ордеру уже есть частичное выполнение, выход
                    raise self.ScriptQuitCondition(
                        'Выход, продолжаем надеяться запасти валюту по тому курсу, по которому уже запасли часть')
                else:
                    logging.debug('Частично исполненных ордеров нет')

                    self.check_reserve_order(order)

        else:  # Открытых ордеров нет
            balances = self._api.get_balances()
            if self.check_balance_for_profit_order(balances):  # Есть ли в наличии CURRENCY_1, которую можно продать?
                self.create_profit_order(balances)
            else:
                # CURRENCY_1 нет, надо докупить
                # Достаточно ли денег на балансе в валюте CURRENCY_2 (Баланс >= CAN_SPEND)
                if self.check_balance_for_reserve_order(balances):
                    self.create_reserve_order()
                else:
                    raise self.ScriptQuitCondition('Выход, не хватает денег')

    def check_reserve_order(self, order):
        time_passed = time.time() + self._stock_time_offset * 60 * 60 - int(order['created'])
        if time_passed > self._order_life_time:
            my_need_price = self.get_desired_reserve_price()
            if math.fabs(my_need_price - float(order['price'])) > float(
                    order['price']) * self._reserve_price_distribution:
                # Ордер уже давно висит, никому не нужен, отменяем
                self._api.cancel_order(order['order_id'])
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
        my_amount = self.calculate_desired_reserve_amount(my_need_price)
        if my_amount >= self._currency_1_min_deal_size:
            logging.info('%s %s %s', self.profit_order_type(), str(my_amount), str(my_need_price))
            new_order = self._api.create_order(
                currency_1=self._currency_1,
                currency_2=self._currency_2,
                quantity=my_amount,
                price=my_need_price,
                type=self.reserve_order_type()
            )
            logging.info(str(new_order))
            logging.debug('Создан ордер на покупку %s', str(new_order['order_id']))

        else:  # мы можем купить слишком мало на нашу сумму
            raise self.ScriptQuitCondition('Выход, не хватает денег на создание ордера')

    def create_profit_order(self, balances):
        """
                        Высчитываем курс для продажи.
                        Нам надо продать всю валюту, которую купили, на сумму, за которую купили + немного навара и минус комиссия биржи
                        При этом важный момент, что валюты у нас меньше, чем купили - бирже ушла комиссия
                        0.00134345 1.5045
                    """
        quantity = self.calculate_profit_quantity(balances)
        price = self.calculate_profit_price(quantity, balances)
        logging.info('%s %s for %s', str(self.profit_order_type()), str(quantity), str(price),
                     str(price))
        new_order = self._api.create_order(
            currency_1=self._currency_1,
            currency_2=self._currency_2,
            quantity=quantity,
            price=price,
            type=self.profit_order_type()
        )
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

    def calculate_desired_reserve_amount(self, my_need_price):
        if self._profile == Profiles.UP:
            return self._currency_2_deal_size / my_need_price
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

    def calculate_profit_quantity(self, balances):
        if self._profile == Profiles.UP:
            return float(balances[self._currency_1])
        elif self._profile == Profiles.DOWN:
            return self._currency_1_deal_size + self._currency_1_deal_size * (
            self._stock_fee + self._spend_profit_markup)
        raise ValueError

    def calculate_profit_price(self, quantity, balances):
        if self._profile == Profiles.UP:
            return (self._currency_2_deal_size / (1 -
                                                  self._stock_fee - self._spend_profit_markup)) / quantity
        elif self._profile == Profiles.DOWN:
            return float(balances[self._currency_2]) / quantity
        raise ValueError
