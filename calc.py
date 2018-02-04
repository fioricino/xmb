import argparse
import sys
from collections import Counter
from collections import defaultdict
from datetime import timedelta, datetime
from pprint import pprint

from exmo_api import ExmoApi
from sqlite_api import SQLiteStorage

FEE = 0.002

PERIOD = timedelta(hours=19)
START_TIME = datetime(2018, 2, 3, 0, 0, 0)

ORDER_FILE = r'real_run\orders.db'

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-k', '--key', type=str, help='Api key')
    parser.add_argument('-s', '--secret', type=str, help='Api secret')
    sysargs = parser.parse_args(sys.argv[1:])

    exmo_api = ExmoApi(sysargs.key, sysargs.secret)

    orders = {}

    st = SQLiteStorage(ORDER_FILE)
    stored_orders = st.get_open_orders()
    for order in stored_orders:
        orders[order['order_id']] = order
    archive_orders = st.get_archive_completed_orders()
    for order in archive_orders:
        orders[order['order_id']] = order

    ds = exmo_api.get_user_trades('BTC', 'USD', limit=200)
    deals = defaultdict(list)
    for d in ds:
        deals[str(d['order_id'])].append(d)

    ok_deals = {}

    c = Counter()

    for order_id, dealset in deals.items():
        if order_id not in orders:
            continue
        order = orders[order_id]
        if order is None or order['status'] != 'COMPLETED':
            continue
        if order['order_type'] == 'PROFIT':
            continue
        else:
            related_orders = [o for o in orders.values() if 'base_order_id' in o
                              and str(o['base_order_id']) == order_id and o['status'] == 'COMPLETED']
        if not related_orders:
            continue
        ok_related_deals = []
        related_orders_ok = True
        for related_order in related_orders:
            related_order_id = str(related_order['order_id'])
            if related_order_id not in deals:
                related_orders_ok = False
                break
            related_dealset = deals[related_order_id]
            for deal in dealset:
                for related_deal in related_dealset:
                    if datetime.fromtimestamp(int(deal['date'])) >= START_TIME and datetime.fromtimestamp(
                            int(related_deal['date'])) > START_TIME:
                        ok_related_deals.append(deal)
                        ok_related_deals.append(related_deal)
                    else:
                        related_orders_ok = False
        if related_orders_ok:
            for d in ok_related_deals:
                ok_deals[d['trade_id']] = d

    pprint(ok_deals)

    for d in ok_deals.values():
        if d['type'] == 'buy':
            c['BTC'] += float(d['quantity']) * (1 - FEE)
            c['USD'] -= float(d['price']) * float(d['quantity'])
        else:
            c['BTC'] -= float(d['quantity'])
            c['USD'] += float(d['price']) * float(d['quantity']) * (1 - FEE)

    print(c)






