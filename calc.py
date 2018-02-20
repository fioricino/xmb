from collections import Counter
from datetime import datetime


class Calc:
    def __init__(self, api, storage, start_time, fee):
        self._api = api
        self._storage = storage
        self._start_time = start_time
        self._fee = fee

    def get_profit(self):
        orders = {}

        # stored_orders = self._storage.get_open_orders()
        # for order in stored_orders:
        #     orders[order['order_id']] = order
        archive_orders = self._storage.get_archive_completed_orders()
        for order in archive_orders:
            orders[order['order_id']] = order

        # ds = self._api.get_user_trades('BTC', 'USD', limit=1000)
        # deals = defaultdict(list)
        # for d in ds:
        #     deals[str(d['order_id'])].append(d)

        ok_deals = {}

        c = Counter()

        for order_id, order in orders.items():
            if order is None or order['status'] != 'COMPLETED':
                continue
            if order['order_type'] == 'RESERVE':
                continue
            else:
                base_order = orders[str(order['base_order_id'])]
                if not base_order:
                    continue
                if order['completed'] is not None and datetime.fromtimestamp(
                        int(order['completed'])) > self._start_time:
                    ok_deals[order_id] = order
                    ok_deals[base_order['order_id']] = base_order
                    # pprint(ok_deals)

        for d in ok_deals.values():
            if d['type'] == 'buy':
                c['BTC'] += float(d['quantity']) * (1 - self._fee)
                c['USD'] -= float(d['price']) * float(d['quantity'])
            else:
                c['BTC'] -= float(d['quantity'])
                c['USD'] += float(d['price']) * float(d['quantity']) * (1 - self._fee)

        return ok_deals, c
