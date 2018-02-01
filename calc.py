import json
import logging
import os
from collections import Counter
from datetime import timedelta, datetime
from decimal import Decimal

import argparse

import sys
from pprint import pprint

from exmo_api import ExmoApi
from json_api import JsonStorage

FEE = 0.002

PERIOD = timedelta(hours=19)
START_TIME = datetime(2018, 1, 31, 21, 00, 00)

ORDER_FILE = r'real_run\orders.json'
ARCHIVE_FOLDER = r'real_run\archive'

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-k', '--key', type=str, help='Api key')
    parser.add_argument('-s', '--secret', type=str, help='Api secret')
    sysargs = parser.parse_args(sys.argv[1:])

    exmo_api = ExmoApi(sysargs.key, sysargs.secret)

    orders = {}
    with open(ORDER_FILE, 'r') as f:
        fl = json.load(f)
        orders.update(fl)
    for a in os.listdir(ARCHIVE_FOLDER):
        with open(os.path.join(ARCHIVE_FOLDER, a)) as f:
            order = json.load(f)
            orders[str(order['order_id'])] = order

    ds = exmo_api.get_user_trades('BTC', 'USD', limit=200)
    deals = {str(d['order_id']) : d for d in ds}

    ok_deals = []

    pprint(deals)
    c = Counter()

    for order_id, deal in deals.items():
        if order_id not in orders:
            continue
        order = orders[order_id]
        if order is None or order['status'] != 'COMPLETED':
            continue
        if order['order_type'] == 'PROFIT':
            base_order_id = str(order['base_order']['order_id'])
            if base_order_id in orders:
                related_orders = [orders[base_order_id]]
        else:
            related_orders = [o for o in orders if 'base_order' in o
                              and str(o['base_order']['order_id']) == order_id and o['status'] == 'COMPLETED']
        if not related_orders:
            continue
        related_order = related_orders[0]
        related_deal = deals[str(related_order['order_id'])]
        if datetime.fromtimestamp(int(deal['date'])) >= START_TIME and datetime.fromtimestamp(int(related_deal['date'])) > START_TIME:
            ok_deals.append(deal)
            ok_deals.append(related_deal)


    for d in ok_deals:
        if d['type'] == 'buy':
            c['BTC'] += float(d['quantity']) * (1 - FEE)
            c['USD'] -= float(d['price']) * float(d['quantity'])
        else:
            c['BTC'] -= float(d['quantity'])
            c['USD'] += float(d['price']) * float(d['quantity']) * (1 - FEE)

    print(c)






