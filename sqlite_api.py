from collections import Counter
from datetime import datetime

import peewee
from peewee import *

database_proxy = peewee.Proxy()


class BaseModel(Model):
    class Meta:
        database = database_proxy


class BaseOrder(BaseModel):
    order_id = CharField(unique=True)
    status = CharField()
    profile = CharField()
    created = DateTimeField()
    completed = DateTimeField(null=True)
    order_type = CharField()
    type = CharField()
    price = FloatField()
    quantity = FloatField()
    pair = CharField(null=True)
    amount = FloatField(null=True)
    trade_id = CharField(null=True)
    profit_markup = FloatField(null=True)


class Order(BaseOrder):
    base_order = ForeignKeyField('self', null=True, to_field='order_id')


class ArchiveOrder(BaseOrder):
    base_order = ForeignKeyField('self', null=True, to_field='order_id')


class SQLiteStorage:
    def __init__(self, db_path):
        self._db = peewee.SqliteDatabase(db_path)
        database_proxy.initialize(self._db)
        self._db.connect(reuse_if_open=True)
        if not self._db.table_exists(Order):
            self._db.create_tables([Order])
        if not self._db.table_exists(ArchiveOrder):
            self._db.create_tables([ArchiveOrder])

    def create_order(self, order, profile, order_type, created, base_order=None, profit_markup=None):
        ord = Order.create(
            order_id=order['order_id'],
            status='OPEN',
            profile=profile,
            created=datetime.fromtimestamp(created),
            completed=datetime.fromtimestamp(int(order['completed'])) if 'completed' in order else None,
            order_type=order_type,
            type=order['type'],
            price=float(order['price']),
            quantity=float(order['quantity']),
            trade_id=order['trade_id'] if 'trade_id' in order else None,
            pair=order['pair'] if 'pair' in order else None,
            amount=float(order['amount']) if 'amount' in order else None,
            profit_markup=profit_markup,
            base_order=base_order['order_id'] if base_order is not None else None
        )
        ord.save()
        return self._map_order(ord)

    def get_open_orders(self):
        ords = Order.select()
        return [self._map_order(o) for o in ords]

    def get_archive_completed_orders(self):
        ords = ArchiveOrder.select().where(
            (ArchiveOrder.status == 'COMPLETED') | (ArchiveOrder.status == 'WAIT_FOR_PROFIT'))
        return [self._map_order(o) for o in ords]

    def _map_order(self, ord, is_archive=False):
        if ord is None:
            return None
        order = {'order_id': str(ord.order_id),
                 'status': ord.status,
                 'profile': ord.profile,
                 'created': int(ord.created.timestamp()),
                 'completed': int(ord.completed.timestamp()) if ord.completed is not None else None,
                 'order_type': ord.order_type,
                 'type': ord.type,
                 'price': ord.price,
                 'quantity': ord.quantity,
                 'pair': ord.pair,
                 'amount': ord.amount,
                 'profit_markup': ord.profit_markup,
                 'trade_id': ord.trade_id,
                 'base_order': self._map_order(ord.base_order)}
        return order

    def delete(self, order_id, status, completed):
        order = Order.get(Order.order_id == str(order_id))
        # if order.base_order is not None:
        #     self.delete(order.base_order.order_id, status, completed)
        archive_order = ArchiveOrder(order_id=order.order_id,
                                     status=order.status,
                                     profile=order.profile,
                                     created=order.created,
                                     completed=order.completed,
                                     type=order.type,
                                     order_type=order.order_type,
                                     price=order.price,
                                     quantity=order.quantity,
                                     trade_id=order.trade_id,
                                     pair=order.pair,
                                     amount=order.amount,
                                     profit_markup=order.profit_markup,
                                     base_order=order.base_order)
        archive_order.status = status
        if order.order_type == 'PROFIT' and order.status == 'COMPLETED' \
                or order.status == 'CANCELED':
            archive_order.completed = datetime.fromtimestamp(completed)
        archive_order.save()
        Order.delete_instance(order)

    def cancel_order(self, order_id, canceled):
        self.delete(str(order_id), 'CANCELED', canceled)

    def update_order_status(self, order_id, status, timestamp, trade_id=None):
        order = Order.get(order_id=str(order_id))
        order.status = status
        if status == 'WAIT_FOR_PROFIT':
            order.completed = datetime.fromtimestamp(timestamp)
        if trade_id is not None:
            order.trade_id = trade_id
        order.save()

    def get_stats(self, start=None, stop=None):
        stats = Counter()
        completed_profit_orders = ArchiveOrder.select().where(ArchiveOrder.order_type == 'PROFIT',
                                                              ArchiveOrder.status == 'COMPLETED')
        for order in completed_profit_orders:
            stats[order.profile] += order.profit_markup
        return stats

# if __name__ == '__main__':
#     st = SQLiteStorage('sqltest.db')
#     # st.create_order({'order_id': '123', 'status': 'OPEN', 'profile': 'UP', 'created': int(time.time()),
#     #                  'order_type': 'RESERVE', 'price': '123.45', 'quantity': '0.0001'}, None)
#     # st.create_order({'order_id': '124', 'status': 'OPEN', 'profile': 'UP', 'created': int(time.time()),
#     #                  'order_type': 'PROFIT', 'price': '123.45', 'quantity': '0.0001'}, '123')
#     st.delete('124', 'COMPLETED', int(datetime.now().timestamp()))
#     orders = st.get_open_orders()
#     i = 0
