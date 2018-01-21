import hashlib
import hmac
import http.client
import json
import logging
import time
import urllib
import urllib.parse

# ключи API, которые предоставила exmo
import math

API_KEY = 'K-020d1e06761624afa1ca3d2a579089746968dfc4'
# обратите внимание, что добавлена 'b' перед строкой
API_SECRET = b'S-9b85d0a24d107ce1d0fd6c516f609debc605aefc'

# Тонкая настройка
CURRENCY_1 = 'BTC'
CURRENCY_2 = 'USD'

CURRENCY_1_MIN_QUANTITY = 0.001  # минимальная сумма ставки - берется из https://api.exmo.com/v1/pair_settings/

ORDER_LIFE_TIME = 0.1  # через сколько минут отменять неисполненный ордер на покупку CURRENCY_1
STOCK_FEE = 0.002  # Комиссия, которую берет биржа (0.002 = 0.2%)
AVG_PRICE_PERIOD = 15  # За какой период брать среднюю цену (мин)
CAN_SPEND = 15.9  # Сколько тратить CURRENCY_2 каждый раз при покупке CURRENCY_1
PROFIT_MARKUP = 0.0005  # Какой навар нужен с каждой сделки? (0.001 = 0.1%)
PROFIT_MARKUP_2 = 0.002  # Какой навар нужен с каждой сделки? (0.001 = 0.1%)
DEBUG = True  # True - выводить отладочную информацию, False - писать как можно меньше
logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level='DEBUG')
BUY_PRICE_DISTRIBUTION = 0.001
MAX_PARALLEL_SELLS = 5  # Максимальное количество параллельных ордеров на продажу
DECREASE_FOR_NEW_SELL = 0.1  # При каком снижении курса можно делать параллельную закупку - 10%

STOCK_TIME_OFFSET = 0  # Если расходится время биржи с текущим

# базовые настройки
API_URL = 'api.exmo.me'
API_VERSION = 'v1'

CURRENT_PAIR = CURRENCY_1 + '_' + CURRENCY_2
CURRENCY_1_DONT_TOUCH = 0.00115176


# Реализация алгоритма
def main_flow():
    try:
        # Получаем список активных ордеров
        try:
            opened_orders = call_api('user_open_orders')[CURRENCY_1 + '_' + CURRENCY_2]
        except KeyError:
            logging.debug('Открытых ордеров нет')
            opened_orders = []

        sell_orders = []
        # Есть ли неисполненные ордера на продажу CURRENCY_1?
        for order in opened_orders:
            if order['type'] == 'sell':
                # if order['order_id'] != '499329939':
                # Есть неисполненные ордера на продажу CURRENCY_1, выход
                raise ScriptQuitCondition(
                    'Выход, ждем пока не исполнятся/закроются все ордера на продажу (один ордер может быть разбит биржей на несколько и исполняться частями)')
            else:
                # Запоминаем ордера на покупку CURRENCY_1
                sell_orders.append(order)

        # Проверяем, есть ли открытые ордера на покупку CURRENCY_1
        if sell_orders:  # открытые ордера есть
            for order in sell_orders:
                # Проверяем, есть ли частично исполненные
                logging.debug('Проверяем, что происходит с отложенным ордером %s', str(get_order_id(order)))
                try:
                    order_history = call_api('order_trades', order_id=get_order_id(order))
                    # по ордеру уже есть частичное выполнение, выход
                    raise ScriptQuitCondition(
                        'Выход, продолжаем надеяться докупить валюту по тому курсу, по которому уже купили часть')
                except ScriptError as e:
                    if 'Error 50304' in str(e):
                        logging.debug('Частично исполненных ордеров нет')

                        time_passed = time.time() + STOCK_TIME_OFFSET * 60 * 60 - int(order['created'])

                        if time_passed > ORDER_LIFE_TIME * 60:
                            my_amount, my_need_price = get_desired_buy_price()
                            if math.fabs(my_need_price - float(order['price'])) > float(
                                    order['price']) * BUY_PRICE_DISTRIBUTION:
                                # Ордер уже давно висит, никому не нужен, отменяем
                                call_api('order_cancel', order_id=get_order_id(order))
                                raise ScriptQuitCondition(
                                    'Отменяем ордер -за ' + str(ORDER_LIFE_TIME) + ' минут не удалось купить ' + str(
                                        CURRENCY_1))
                            else:
                                logging.debug('Не отменяем ордер, так как курс не изменился: %s.', my_need_price)
                        else:
                            raise ScriptQuitCondition(
                                'Выход, продолжаем надеяться купить валюту по указанному ранее курсу, со времени создания ордера прошло %s секунд' % str(
                                    time_passed))
                    else:
                        raise ScriptQuitCondition(str(e))

        else:  # Открытых ордеров нет
            balances = call_api('user_info')['balances']
            if get_currency_1_balance(
                    balances) >= CURRENCY_1_MIN_QUANTITY:  # Есть ли в наличии CURRENCY_1, которую можно продать?
                """
                    Высчитываем курс для продажи.
                    Нам надо продать всю валюту, которую купили, на сумму, за которую купили + немного навара и минус комиссия биржи
                    При этом важный момент, что валюты у нас меньше, чем купили - бирже ушла комиссия
                    0.00134345 1.5045
                """
                wanna_get = CAN_SPEND + CAN_SPEND * (
                    STOCK_FEE + PROFIT_MARKUP_2)  # сколько хотим получить за наше кол-во
                logging.info('sell %s %s %s', str(get_currency_1_balance(balances)), str(wanna_get),
                             str((wanna_get / get_currency_1_balance(
                                 balances))))
                new_order = call_api(
                    'order_create',
                    pair=CURRENT_PAIR,
                    quantity=balances[CURRENCY_1],
                    price=wanna_get / get_currency_1_balance(balances),
                    type='sell'
                )
                logging.info(str(new_order))
                logging.debug('Создан ордер на продажу %s %s', CURRENCY_1, str(get_order_id(new_order)))
            else:
                # CURRENCY_1 нет, надо докупить
                # Достаточно ли денег на балансе в валюте CURRENCY_2 (Баланс >= CAN_SPEND)
                if float(balances[CURRENCY_2]) >= CAN_SPEND:
                    my_amount, my_need_price = get_desired_buy_price()
                    create_order_if_enough_money(my_amount, my_need_price)
                else:
                    raise ScriptQuitCondition('Выход, не хватает денег')

    except ScriptError as e:
        logging.error(str(e))
    except ScriptQuitCondition as e:
        logging.debug(str(e))
        pass
    except Exception as e:
        logging.fatal(str(e))


def get_currency_1_balance(balances):
    return float(balances[CURRENCY_1])  # - CURRENCY_1_DONT_TOUCH


def get_order_id(order):
    return order['order_id']


def create_order_if_enough_money(my_amount, my_need_price):
    # Допускается ли покупка такого кол-ва валюты (т.е. не нарушается минимальная сумма сделки)
    if my_amount >= CURRENCY_1_MIN_QUANTITY:
        logging.info('buy %s %s', str(my_amount), str(my_need_price))
        create_order(my_amount, my_need_price)

    else:  # мы можем купить слишком мало на нашу сумму
        raise ScriptQuitCondition('Выход, не хватает денег на создание ордера')


def create_order(my_amount, my_need_price):
    new_order = call_api(
        'order_create',
        pair=CURRENT_PAIR,
        quantity=my_amount,
        price=my_need_price,
        type='buy'
    )
    logging.info(str(new_order))
    logging.debug('Создан ордер на покупку %s', str(new_order['order_id']))


def get_desired_buy_price():
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
    deals = call_api('trades', pair=CURRENT_PAIR)
    # prices = []
    amount = 0
    quantity = 0
    for deal in deals[CURRENT_PAIR]:
        time_passed = time.time() + STOCK_TIME_OFFSET * 60 * 60 - int(deal['date'])
        if time_passed < AVG_PRICE_PERIOD * 60:
            # prices.append(float(deal['price']))
            amount += float(deal['amount'])
            quantity += float(deal['quantity'])
            if quantity == 0:
                raise ScriptQuitCondition('Не удается вычислить среднюю цену')
    avg_price = amount / quantity
    """
                            Посчитать, сколько валюты CURRENCY_1 можно купить.
                            На сумму CAN_SPEND за минусом STOCK_FEE, и с учетом PROFIT_MARKUP
                            ( = ниже средней цены рынка, с учетом комиссии и желаемого профита)
                        """
    # купить больше, потому что биржа потом заберет кусок
    my_need_price = avg_price - avg_price * (STOCK_FEE + PROFIT_MARKUP)
    my_amount = CAN_SPEND / my_need_price
    return my_amount, my_need_price


def call_api(api_method, http_method="POST", **kwargs):
    payload = {'nonce': int(round(time.time() * 1000))}

    if kwargs:
        payload.update(kwargs)
    payload = urllib.parse.urlencode(payload)

    H = hmac.new(key=API_SECRET, digestmod=hashlib.sha512)
    H.update(payload.encode('utf-8'))
    sign = H.hexdigest()

    headers = {"Content-type": "application/x-www-form-urlencoded",
               "Key": API_KEY,
               "Sign": sign}
    conn = http.client.HTTPSConnection(API_URL, timeout=60)
    conn.request(http_method, "/" + API_VERSION + "/" + api_method, payload, headers)
    response = conn.getresponse().read()
    conn.close()
    try:
        obj = json.loads(response.decode('utf-8'))
        if 'error' in obj and obj['error']:
            raise ScriptError(obj['error'])
        return obj
    except json.decoder.JSONDecodeError:
        raise ScriptError('Ошибка анализа возвращаемых данных, получена строка', response)


class ScriptError(Exception):
    pass


class ScriptQuitCondition(Exception):
    pass


if __name__ == '__main__':
    while True:
        main_flow()
        time.sleep(1)
