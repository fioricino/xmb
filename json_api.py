import json
import logging
import os
import os.path


class JsonStorage:
    def __init__(self):
        self.orders = {}

    def delete(self, order_id, status):
        logging.debug('Archive order %s with status %s', order_id, status)
        order_to_store = self.orders[order_id]
        order_to_store['status'] = status
        self.save_to_disk(order_to_store, os.path.join('archive', order_id + 'json'))
        self.orders.pop(order_id)

    def cancel_order(self, order_id):
        self.delete(order_id, 'CANCELED')

    def update_order_status(self, order_id, status):
        order = self.orders[order_id]
        order['status'] = 'WAIT_FOR_PROFIT'
        self.save_orders()

    def get_open_orders(self):
        return self.orders.values()

    def create_order(self, order, profile, order_type, base_order=None):
        order_to_store = {
            'order_data': order,
            'profile': profile.name,
            'order_type': order_type,
            'status': 'OPEN',
            'base_order': base_order
        }
        logging.debug('Save order: %s', order_to_store)
        self.orders[order['order_id']] = order_to_store
        self.save_orders()

    def save_orders(self):
        self.save_to_disk(self.orders, os.path.join('data', 'orders.json'))

    def save_to_disk(self, obj, path):
        json.dump(obj, path)
