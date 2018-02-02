import argparse
import json
import os
import sys
from collections import Counter
from datetime import timedelta, datetime
from pprint import pprint

from exmo_api import ExmoApi

FEE = 0.002

PERIOD = timedelta(hours=19)
START_TIME = datetime(2018, 2, 1, 22, 15, 00)

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

    # pprint(deals)
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
        ok_related_deals = []
        for related_order in related_orders:
            related_order_id = str(related_order['order_id'])
            if related_order_id not in deals:
                continue
            related_deal = deals[related_order_id]
            if datetime.fromtimestamp(int(deal['date'])) >= START_TIME and datetime.fromtimestamp(
                    int(related_deal['date'])) > START_TIME:
                ok_related_deals.append(deal)
                ok_related_deals.append(related_deal)
            else:
                continue
        ok_deals.extend(ok_related_deals)

    pprint(ok_deals)

    for d in ok_deals:
        if d['type'] == 'buy':
            c['BTC'] += float(d['quantity']) * (1 - FEE)
            c['USD'] -= float(d['price']) * float(d['quantity'])
        else:
            c['BTC'] -= float(d['quantity'])
            c['USD'] += float(d['price']) * float(d['quantity']) * (1 - FEE)

    print(c)






