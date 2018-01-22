from collections import Counter
from decimal import Decimal

from exmo_api import ExmoApi

FEE = Decimal('0.002')


def get_cf(order_type, currency):
    if order_type == 'sell':
        if currency == 'btc':
            return 1
        elif currency == 'usd':
            return 1 - FEE
    elif order_type == 'buy':
        if currency == 'btc':
            return 1 - FEE
        elif currency == 'usd':
            return 1
    raise ValueError()


def get_sign(order_type, currency):
    if order_type == 'sell':
        if currency == 'btc':
            return -1
        elif currency == 'usd':
            return 1
    elif order_type == 'buy':
        if currency == 'btc':
            return 1
        elif currency == 'usd':
            return -1
    raise ValueError()


def calculate_deal(deal):
    btc_cf = get_cf(deal['type'], 'btc')
    usd_cf = get_cf(deal['type'], 'usd')

    btc_sign = get_sign(deal['type'], 'btc')
    usd_sign = get_sign(deal['type'], 'usd')

    btc_transfer = btc_cf * Decimal(deal['quantity']) * btc_sign
    usd_transfer = usd_cf * Decimal(deal['quantity']) * usd_sign * Decimal(deal['price'])

    return btc_transfer, usd_transfer


def calculate_profit(deals):
    c = Counter()
    last_price = Decimal(deals[0]['price'])
    last_usd_amount = Decimal(deals[0]['amount'])
    for deal in deals:
        btc_amount, usd_amount = calculate_deal(deal)
        c['btc'] += btc_amount
        c['usd'] += usd_amount
        c['btc_in_usd'] = Decimal(c['btc']) * last_price
        c['profit'] = c['usd'] + c['btc_in_usd']
        c['profit_percent'] = c['profit'] / last_usd_amount * 100
    return c


if __name__ == '__main__':
    deals = ExmoApi().get_trades('BTC', 'USD')
    if deals:
        c = calculate_profit(deals)
        print(c)
        print('USD: {}'.format(c['usd']))
        print('BTC: {}'.format(c['btc']))
        print('BTC IN USD: {}'.format(c['btc_in_usd']))
        print('Profit USD: {}'.format(c['profit']))
        print('Profit %: {}'.format(c['profit_percent']))
