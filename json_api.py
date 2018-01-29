import json
import logging
import os
import os.path
from collections import Counter

logger = logging.getLogger('xmb')

class JsonStorage:
    def __init__(self, order_file='', archive_folder=''):
        self._order_file = order_file
        self._archive_folder = archive_folder
        self.orders = self.load_orders_from_disk()

    def delete(self, order_id, status, completed):
        logger.debug('Archive order {} with status {}'.format(order_id, status))
        order_to_store = self.orders[order_id]
        order_to_store['status'] = status
        if order_to_store['order_type'] == 'PROFIT' and status == 'COMPLETED' or order_to_store['status'] == 'CANCELED':
            order_to_store['completed'] = completed
        self.save_to_disk(order_to_store, os.path.join(self._archive_folder, str(order_id) + '.json'))
        self.orders.pop(order_id)
        self.save_orders()

    def cancel_order(self, order_id, canceled):
        self.delete(order_id, 'CANCELED', canceled)

    def update_order_status(self, order_id, status, timestamp):
        order = self.orders[order_id]
        order['status'] = status
        if status == 'WAIT_FOR_PROFIT':
            order['completed'] = timestamp
        self.save_orders()

    def get_open_orders(self):
        return self.orders.values()

    def create_order(self, order, profile, order_type, created, base_order=None, profit_markup=None):
        order_to_store = {
            'order_id': order['order_id'],
            'order_data': order,
            'profile': profile,
            'order_type': order_type,
            'status': 'OPEN',
            'base_order': base_order,
            'profit_markup': profit_markup,
            'created': created
        }
        logger.debug('Save order: %s', order_to_store)
        self.orders[order['order_id']] = order_to_store
        self.save_orders()
        return order_to_store

    def save_orders(self):
        self.save_to_disk(self.orders, self._order_file)

    def get_stats(self, start=None, stop=None):
        stats = Counter()
        for filename in os.listdir(self._archive_folder):
            with open(os.path.join(self._archive_folder, filename)) as f:
                d = json.load(f)
                # TODO check time
                if d['order_type'] == 'PROFIT' and d['status'] == 'COMPLETED':
                    stats[d['profile']] += float(d['profit_markup'])
        return stats


    def save_to_disk(self, obj, path):
        try:
            with open(path, 'w') as f:
                json.dump(obj, f, indent=4)
        except Exception:
            logger.exception('Cannot save archive')

    def load_orders_from_disk(self):
        try:
            with open(self._order_file, 'r') as f:
                return json.load(f)
        except:
            logger.exception('Cannot read orders')
            return {}
