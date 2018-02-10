from collections import Counter
from collections import defaultdict
from datetime import datetime


class Calc:
    def __init__(self, api, storage, start_time, fee):
        self._api = api
        self._storage = storage
        self._start_time = start_time
        self._fee = fee

    def get_profit(self):
        orders = {}

        stored_orders = self._storage.get_open_orders()
        for order in stored_orders:
            orders[order['order_id']] = order
        archive_orders = self._storage.get_archive_completed_orders()
        for order in archive_orders:
            orders[order['order_id']] = order

        ds = self._api.get_user_trades('BTC', 'USD', limit=1000)
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
                        # if datetime.fromtimestamp(int(deal['date'])) >= self._start_time and \
                        if datetime.fromtimestamp(
                                int(related_deal['date'])) > self._start_time:
                            ok_related_deals.append(deal)
                            ok_related_deals.append(related_deal)
                        else:
                            related_orders_ok = False
            if related_orders_ok:
                for d in ok_related_deals:
                    ok_deals[d['trade_id']] = d

        # pprint(ok_deals)

        for d in ok_deals.values():
            if d['type'] == 'buy':
                c['BTC'] += float(d['quantity']) * (1 - self._fee)
                c['USD'] -= float(d['price']) * float(d['quantity'])
            else:
                c['BTC'] -= float(d['quantity'])
                c['USD'] += float(d['price']) * float(d['quantity']) * (1 - self._fee)

        return ok_deals, c
