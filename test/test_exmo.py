import json
import time
import unittest

from exmo_general import Worker, Profiles
from json_api import JsonStorage


class StorageMock(JsonStorage):
    def __init__(self):
        super(StorageMock, self).__init__()
        self.archive = {}

    def save_to_disk(self, obj, path):
        pass

    def delete(self, order_id, status):
        super(StorageMock, self).delete(order_id, status)
        self.archive[order_id] = status


class TestWorker(unittest.TestCase):

    def test_get_avg_price(self):
        class ApiMock():
            def get_trades(self, currency_1, currency_2):
                return [{'date': str(int(time.time()) - 100), 'amount': 200, 'quantity': 1},
                        {'date': str(int(time.time()) - 200), 'amount': 400, 'quantity': 2},
                        {'date': str(int(time.time()) - 100), 'amount': 500, 'quantity': 4},
                        {'date': str(int(time.time()) - 100), 'amount': 300, 'quantity': 2},
                        {'date': str(int(time.time()) - 100), 'amount': 100, 'quantity': 1},
                        # must be ignored as outdated
                        {'date': str(int(time.time()) - 1000), 'amount': 1000, 'quantity': 1}]

        worker = Worker(ApiMock(), None, profile=None, avg_price_period=900)
        self.assertEqual(150, worker.get_avg_price())

    def test_get_desired_reserve_price_up(self):
        worker = Worker(None, None, profile=Profiles.UP, stock_fee=0.25)
        need_price = worker.calculate_desired_reserve_price(100)
        self.assertEqual(80, need_price)

    def test_get_desired_reserve_amount_up(self):
        worker = Worker(None, None, profile=Profiles.UP, stock_fee=0.2, currency_1_deal_size=4)
        amount = worker.calculate_desired_reserve_amount()
        self.assertEqual(5, amount)

    def test_get_desired_reserve_price_down(self):
        worker = Worker(None, None, profile=Profiles.DOWN, stock_fee=0.2, currency_1_deal_size=5)
        need_price = worker.calculate_desired_reserve_price(100)
        self.assertEqual(125, need_price)

    def test_get_desired_reserve_amount_down(self):
        worker = Worker(None, None, profile=Profiles.DOWN, stock_fee=0.05, currency_1_deal_size=5)
        amount = worker.calculate_desired_reserve_amount()
        self.assertEqual(5, amount)

    def test_main_flow_open_profit_order_up(self):
        # Проверяем, что процесс выходит, если игра на повышение и есть открытый ордер на продажу
        order_id = '123'
        order = {'order_id': order_id, 'type': 'sell'}

        class ApiMock:
            def __init__(self):
                self.get_open_orders_called = 0

            def get_open_orders(self, currency_1, currency_2):
                self.get_open_orders_called += 1
                return [order]

        api = ApiMock()
        storage = StorageMock()
        stored_order = {'status': 'OPEN', 'order_data': order, 'order_type': 'PROFIT', 'profile': 'UP'}
        stored_order_s = json.dumps(stored_order)
        storage.orders[order_id] = stored_order
        worker = Worker(api, storage, profile=Profiles.UP)
        self.assertRaises(Worker.ScriptQuitCondition, worker.main_flow)

        self.assertEqual(1, api.get_open_orders_called)
        self.assertEqual(stored_order_s, json.dumps(storage.orders[order_id]))

    def test_main_flow_open_profit_order_down(self):
        # Проверяем, что процесс выходит, если игра на повышение и есть открытый ордер на продажу
        order_id = '123'
        order = {'order_id': order_id, 'type': 'buy'}

        class ApiMock:
            def __init__(self):
                self.get_open_orders_called = 0

            def get_open_orders(self, currency_1, currency_2):
                self.get_open_orders_called += 1
                return [order]

        api = ApiMock()
        storage = StorageMock()
        stored_order = {'status': 'OPEN', 'order_data': order, 'order_type': 'PROFIT', 'profile': 'DOWN'}
        stored_order_s = json.dumps(stored_order)
        storage.orders[order_id] = stored_order
        worker = Worker(api, storage, profile=Profiles.DOWN)
        self.assertRaises(Worker.ScriptQuitCondition, worker.main_flow)

        self.assertEqual(1, api.get_open_orders_called)
        self.assertEqual(stored_order_s, json.dumps(storage.orders[order_id]))

    def test_main_flow_order_partially_completed_up(self):
        # Проверяем, что процесс выходит, если есть частично выполенный ордер на запас
        mock_order_id = '122'
        order = {'type': 'buy', 'order_id': mock_order_id}

        class ApiMock:
            def __init__(self, test):
                self.get_open_orders_called = 0
                self.is_order_partially_completed_called = 0
                self.test = test

            def get_open_orders(self, currency_1, currency_2):
                self.get_open_orders_called += 1
                return [order]

            def is_order_partially_completed(self, order_id):
                self.test.assertEquals(mock_order_id, order_id)
                self.is_order_partially_completed_called += 1
                return True

        storage = StorageMock()
        stored_order = {'status': 'OPEN', 'order_data': order, 'order_type': 'RESERVE', 'profile': 'UP'}
        stored_order_s = json.dumps(stored_order)
        storage.orders[mock_order_id] = stored_order

        api = ApiMock(self)
        worker = Worker(api, storage, profile=Profiles.UP)
        self.assertRaises(Worker.ScriptQuitCondition, worker.main_flow)
        self.assertEqual(1, api.get_open_orders_called)
        self.assertEqual(1, api.is_order_partially_completed_called)
        self.assertEqual(stored_order_s, json.dumps(storage.orders[mock_order_id]))

    def test_main_flow_order_partially_completed_down(self):
        # Проверяем, что процесс выходит, если есть частично выполенный ордер на запас
        mock_order_id = '122'
        order = {'type': 'sell', 'order_id': mock_order_id}

        class ApiMock:
            def __init__(self, test):
                self.get_open_orders_called = 0
                self.is_order_partially_completed_called = 0
                self.test = test

            def get_open_orders(self, currency_1, currency_2):
                self.get_open_orders_called += 1
                return [order]

            def is_order_partially_completed(self, order_id):
                self.test.assertEquals(mock_order_id, order_id)
                self.is_order_partially_completed_called += 1
                return True

        storage = StorageMock()
        stored_order = {'status': 'OPEN', 'order_data': order, 'order_type': 'RESERVE', 'profile': 'DOWN'}
        stored_order_s = json.dumps(stored_order)
        storage.orders[mock_order_id] = stored_order

        api = ApiMock(self)
        worker = Worker(api, storage, profile=Profiles.DOWN)
        self.assertRaises(Worker.ScriptQuitCondition, worker.main_flow)
        self.assertEqual(1, api.get_open_orders_called)
        self.assertEqual(1, api.is_order_partially_completed_called)
        self.assertEqual(stored_order_s, json.dumps(storage.orders[mock_order_id]))

    def test_main_flow_reserve_order_not_outdated_up(self):
        # Проверяем, что процесс выходит, если есть не истекший ордер на запас
        mock_order_id = '122'
        order = {'type': 'buy', 'order_id': mock_order_id, 'created': str(int(time.time() - 10))}

        class ApiMock:
            def __init__(self, test):
                self.get_open_orders_called = 0
                self.is_order_partially_completed_called = 0
                self.test = test

            def get_open_orders(self, currency_1, currency_2):
                self.get_open_orders_called += 1
                return [order]

            def is_order_partially_completed(self, order_id):
                self.test.assertEquals(mock_order_id, order_id)
                self.is_order_partially_completed_called += 1
                return False

        api = ApiMock(self)

        storage = StorageMock()
        stored_order = {'status': 'OPEN', 'order_data': order, 'order_type': 'RESERVE', 'profile': 'UP'}
        stored_order_s = json.dumps(stored_order)
        storage.orders[mock_order_id] = stored_order

        worker = Worker(api, storage, profile=Profiles.UP)
        self.assertRaises(Worker.ScriptQuitCondition, worker.main_flow)

        self.assertEqual(1, api.get_open_orders_called)
        self.assertEqual(1, api.is_order_partially_completed_called)
        self.assertEqual(stored_order_s, json.dumps(storage.orders[mock_order_id]))

    def test_main_flow_reserve_order_not_outdated_down(self):
        # Проверяем, что процесс выходит, если есть не истекший ордер на запас
        mock_order_id = '122'
        order = {'type': 'sell', 'order_id': mock_order_id, 'created': str(int(time.time() - 10))}

        class ApiMock:
            def __init__(self, test):
                self.get_open_orders_called = 0
                self.is_order_partially_completed_called = 0
                self.test = test

            def get_open_orders(self, currency_1, currency_2):
                self.get_open_orders_called += 1
                return [order]

            def is_order_partially_completed(self, order_id):
                self.test.assertEquals(mock_order_id, order_id)
                self.is_order_partially_completed_called += 1
                return False

        api = ApiMock(self)

        storage = StorageMock()
        stored_order = {'status': 'OPEN', 'order_data': order, 'order_type': 'RESERVE', 'profile': 'DOWN'}
        stored_order_s = json.dumps(stored_order)
        storage.orders[mock_order_id] = stored_order

        worker = Worker(api, storage, profile=Profiles.DOWN)
        self.assertRaises(Worker.ScriptQuitCondition, worker.main_flow)

        self.assertEqual(1, api.get_open_orders_called)
        self.assertEqual(1, api.is_order_partially_completed_called)
        self.assertEqual(stored_order_s, json.dumps(storage.orders[mock_order_id]))

    def test_main_flow_reserve_order_outdated_same_price_up(self):
        # Проверяем, что процесс выходит, если есть истекший ордер на запас, но цена не изменилась
        mock_order_id = '122'
        mock_order_price = 150
        order = {'type': 'buy', 'order_id': mock_order_id, 'created': str(int(time.time() - 1000)),
                 'price': str(mock_order_price)}

        class ApiMock:
            def __init__(self, test):
                self.get_open_orders_called = 0
                self.is_order_partially_completed_called = 0
                self.test = test

            def get_open_orders(self, currency_1, currency_2):
                self.get_open_orders_called += 1
                return [order]

            def is_order_partially_completed(self, order_id):
                self.test.assertEquals(mock_order_id, order_id)
                self.is_order_partially_completed_called += 1
                return False

        def get_desired_reserve_price():
            return mock_order_price - 1

        api = ApiMock(self)

        storage = StorageMock()
        stored_order = {'status': 'OPEN', 'order_data': order, 'order_type': 'RESERVE', 'profile': 'UP'}
        stored_order_s = json.dumps(stored_order)
        storage.orders[mock_order_id] = stored_order

        worker = Worker(api, storage, profile=Profiles.UP, reserve_price_distribution=0.1, order_life_time=60)
        worker.get_desired_reserve_price = get_desired_reserve_price
        self.assertRaises(Worker.ScriptQuitCondition, worker.main_flow)

        self.assertEqual(1, api.get_open_orders_called)
        self.assertEqual(1, api.is_order_partially_completed_called)
        self.assertEqual(stored_order_s, json.dumps(storage.orders[mock_order_id]))

    def test_main_flow_reserve_order_outdated_same_price_down(self):
        # Проверяем, что процесс выходит, если есть истекший ордер на запас, но цена не изменилась
        mock_order_id = '122'
        mock_order_price = 150
        order = {'type': 'sell', 'order_id': mock_order_id, 'created': str(int(time.time() - 1000)),
                 'price': str(mock_order_price)}

        class ApiMock:
            def __init__(self, test):
                self.get_open_orders_called = 0
                self.is_order_partially_completed_called = 0
                self.test = test

            def get_open_orders(self, currency_1, currency_2):
                self.get_open_orders_called += 1
                return [order]

            def is_order_partially_completed(self, order_id):
                self.test.assertEqual(mock_order_id, order_id)
                self.is_order_partially_completed_called += 1
                return False

        def get_desired_reserve_price():
            return mock_order_price - 1

        api = ApiMock(self)

        storage = StorageMock()
        stored_order = {'status': 'OPEN', 'order_data': order, 'order_type': 'RESERVE', 'profile': 'DOWN'}
        stored_order_s = json.dumps(stored_order)
        storage.orders[mock_order_id] = stored_order

        worker = Worker(api, storage, profile=Profiles.DOWN, reserve_price_distribution=0.1, order_life_time=60)
        worker.get_desired_reserve_price = get_desired_reserve_price
        self.assertRaises(Worker.ScriptQuitCondition, worker.main_flow)

        self.assertEqual(1, api.get_open_orders_called)
        self.assertEqual(1, api.is_order_partially_completed_called)
        self.assertEqual(stored_order_s, json.dumps(storage.orders[mock_order_id]))

    def test_main_flow_reserve_order_outdated_other_price_up(self):
        # Проверяем, что истекший ордер на запас отменяется, если цена изменилась
        mock_order_id = '122'
        mock_order_price = 150
        order = {'type': 'buy', 'order_id': mock_order_id, 'created': str(int(time.time() - 1000)),
                 'price': str(mock_order_price)}

        class ApiMock:
            def __init__(self, test):
                self.get_open_orders_called = 0
                self.is_order_partially_completed_called = 0
                self.cancel_order_called = 0
                self.test = test

            def get_open_orders(self, currency_1, currency_2):
                self.get_open_orders_called += 1
                return [order]

            def is_order_partially_completed(self, order_id):
                self.test.assertEqual(mock_order_id, order_id)
                self.is_order_partially_completed_called += 1
                return False

            def cancel_order(self, order_id):
                self.cancel_order_called += 1
                return True

        def get_desired_reserve_price():
            return mock_order_price - 50

        api = ApiMock(self)

        storage = StorageMock()
        stored_order = {'status': 'OPEN', 'order_data': order, 'order_type': 'RESERVE', 'profile': 'UP'}
        storage.orders[mock_order_id] = stored_order

        worker = Worker(api, storage, profile=Profiles.UP, reserve_price_distribution=0.1, order_life_time=60)
        worker.get_desired_reserve_price = get_desired_reserve_price
        self.assertRaises(Worker.ScriptQuitCondition, worker.main_flow)

        self.assertEqual(1, api.get_open_orders_called)
        self.assertEqual(1, api.is_order_partially_completed_called)
        self.assertEqual(1, api.cancel_order_called)
        self.assertEqual(0, len(storage.orders))
        self.assertEqual('CANCELED', storage.archive[mock_order_id])

    def test_main_flow_reserve_order_outdated_other_price_down(self):
        # Проверяем, что истекший ордер на запас отменяется, если цена изменилась
        mock_order_id = '122'
        mock_order_price = 150
        order = {'type': 'sell', 'order_id': mock_order_id, 'created': str(int(time.time() - 1000)),
                 'price': str(mock_order_price)}

        class ApiMock:
            def __init__(self, test):
                self.get_open_orders_called = 0
                self.is_order_partially_completed_called = 0
                self.cancel_order_called = 0
                self.test = test

            def get_open_orders(self, currency_1, currency_2):
                self.get_open_orders_called += 1
                return [order]

            def is_order_partially_completed(self, order_id):
                self.test.assertEqual(mock_order_id, order_id)
                self.is_order_partially_completed_called += 1
                return False

            def cancel_order(self, order_id):
                self.cancel_order_called += 1
                return True

        def get_desired_reserve_price():
            return mock_order_price - 50

        api = ApiMock(self)

        storage = StorageMock()
        stored_order = {'status': 'OPEN', 'order_data': order, 'order_type': 'RESERVE', 'profile': 'DOWN'}
        storage.orders[mock_order_id] = stored_order

        worker = Worker(api, storage, profile=Profiles.DOWN, reserve_price_distribution=0.1, order_life_time=60)
        worker.get_desired_reserve_price = get_desired_reserve_price
        self.assertRaises(Worker.ScriptQuitCondition, worker.main_flow)

        self.assertEqual(1, api.get_open_orders_called)
        self.assertEqual(1, api.is_order_partially_completed_called)
        self.assertEqual(1, api.cancel_order_called)
        self.assertEqual(0, len(storage.orders))
        self.assertEqual('CANCELED', storage.archive[mock_order_id])


    def test_main_flow_create_reserve_order_up(self):
        mock_order_id = '122'
        expected_order_type = 'buy'
        expected_price = 50
        expected_quantity = 5
        order = {'order_id': mock_order_id, 'quantity': str(expected_quantity), 'price': str(expected_price),
                 'type': expected_order_type}

        # Проверяем создание ордера на резерв
        class ApiMock:
            def __init__(self, test):
                self.get_open_orders_called = 0
                self.create_order_called = 0
                self.test = test
                self.orders = []

            def get_open_orders(self, currency_1, currency_2):
                self.get_open_orders_called += 1
                return self.orders

            def create_order(self, currency_1, currency_2, quantity, price, type):
                self.test.assertEqual('BTC', currency_1)
                self.test.assertEqual('USD', currency_2)
                self.test.assertEqual(expected_quantity, quantity)
                self.test.assertEqual(expected_price, price)
                self.test.assertEqual(expected_order_type, type)
                self.create_order_called += 1
                self.orders.append(order)
                return mock_order_id

        api = ApiMock(self)
        storage = StorageMock()

        def get_avg_price():
            return 60

        worker = Worker(api, storage, profile=Profiles.UP, currency_1_deal_size=4, stock_fee=0.2)
        worker.get_avg_price = get_avg_price
        worker.main_flow()

        self.assertEqual(2, api.get_open_orders_called)
        self.assertEqual(1, api.create_order_called)
        self.assertTrue(mock_order_id in storage.orders)
        self.assertEquals(order, storage.orders[mock_order_id]['order_data'])
        self.assertEquals('UP', storage.orders[mock_order_id]['profile'])
        self.assertEquals('RESERVE', storage.orders[mock_order_id]['order_type'])
        self.assertEquals('OPEN', storage.orders[mock_order_id]['status'])


    def test_main_flow_create_reserve_order_down(self):
        mock_order_id = '122'
        expected_order_type = 'sell'
        expected_price = 62.5
        expected_quantity = 5
        order = {'order_id': mock_order_id, 'quantity': str(expected_quantity), 'price': str(expected_price),
                 'type': expected_order_type}

        # Проверяем создание ордера на резерв
        class ApiMock:
            def __init__(self, test):
                self.get_open_orders_called = 0
                self.create_order_called = 0
                self.test = test
                self.orders = []

            def get_open_orders(self, currency_1, currency_2):
                self.get_open_orders_called += 1
                return self.orders

            def create_order(self, currency_1, currency_2, quantity, price, type):
                self.test.assertEqual('BTC', currency_1)
                self.test.assertEqual('USD', currency_2)
                self.test.assertEqual(expected_quantity, quantity)
                self.test.assertEqual(expected_price, price)
                self.test.assertEqual(expected_order_type, type)
                self.create_order_called += 1
                self.orders.append(order)
                return mock_order_id

        api = ApiMock(self)
        storage = StorageMock()

        def get_avg_price():
            return 50

        worker = Worker(api, storage, profile=Profiles.DOWN, currency_1_deal_size=5, stock_fee=0.2)
        worker.get_avg_price = get_avg_price
        worker.main_flow()

        self.assertEqual(2, api.get_open_orders_called)
        self.assertEqual(1, api.create_order_called)
        self.assertTrue(mock_order_id in storage.orders)
        self.assertEquals(order, storage.orders[mock_order_id]['order_data'])
        self.assertEquals('DOWN', storage.orders[mock_order_id]['profile'])
        self.assertEquals('RESERVE', storage.orders[mock_order_id]['order_type'])

    def test_main_flow_reserve_order_completed_up(self):
        # Проверяем, что процесс выходит, если есть не истекший ордер на запас
        mock_order_id = '122'
        order = {'type': 'buy', 'order_id': mock_order_id, 'created': str(int(time.time() - 10))}

        class ApiMock:
            def __init__(self, test):
                self.get_open_orders_called = 0
                self.test = test

            def get_open_orders(self, currency_1, currency_2):
                self.get_open_orders_called += 1
                return []

        api = ApiMock(self)

        storage = StorageMock()
        stored_order = {'status': 'OPEN', 'order_data': order, 'order_type': 'RESERVE', 'profile': 'UP'}
        storage.orders[mock_order_id] = stored_order

        worker = Worker(api, storage, profile=Profiles.UP)
        worker.main_flow()

        self.assertEqual(1, api.get_open_orders_called)
        self.assertTrue(mock_order_id in storage.orders)
        self.assertEquals('WAIT_FOR_PROFIT', storage.orders[mock_order_id]['status'])

    def test_main_flow_reserve_order_completed_down(self):
        # Проверяем, что процесс выходит, если есть не истекший ордер на запас
        mock_order_id = '122'
        order = {'type': 'sell', 'order_id': mock_order_id, 'created': str(int(time.time() - 10))}

        class ApiMock:
            def __init__(self, test):
                self.get_open_orders_called = 0
                self.test = test

            def get_open_orders(self, currency_1, currency_2):
                self.get_open_orders_called += 1
                return []

        api = ApiMock(self)

        storage = StorageMock()
        stored_order = {'status': 'OPEN', 'order_data': order, 'order_type': 'RESERVE', 'profile': 'DOWN'}
        storage.orders[mock_order_id] = stored_order

        worker = Worker(api, storage, profile=Profiles.DOWN)
        worker.main_flow()

        self.assertEqual(1, api.get_open_orders_called)
        self.assertTrue(mock_order_id in storage.orders)
        self.assertEquals('WAIT_FOR_PROFIT', storage.orders[mock_order_id]['status'])


    def test_main_flow_create_profit_order_up(self):
        # Проверяем создание ордера на резерв
        base_order_id = '100'
        base_order = {'order_id': base_order_id, 'quantity': 50, 'price': 80, 'type': 'buy'}
        new_order_id = '122'
        expected_order_type = 'sell'
        expected_price = 150
        expected_quantity = 40
        expected_order = {'order_id': new_order_id, 'quantity': str(expected_quantity), 'price': str(expected_price),
                          'type': expected_order_type}

        class ApiMock:
            def __init__(self, test):
                self.get_open_orders_called = 0
                self.create_order_called = 0
                self.test = test
                self.orders = []

            def get_open_orders(self, currency_1, currency_2):
                    self.get_open_orders_called += 1
                    return self.orders

            def create_order(self, currency_1, currency_2, quantity, price, type):
                self.test.assertEqual('BTC', currency_1)
                self.test.assertEqual('USD', currency_2)
                self.test.assertEqual(expected_quantity, quantity)
                self.test.assertEqual(expected_price, price)
                self.test.assertEqual(expected_order_type, type)
                    self.create_order_called += 1
                self.orders.append(expected_order)
                return new_order_id

        api = ApiMock(self)

        storage = StorageMock()
        stored_order = {'status': 'WAIT_FOR_PROFIT', 'order_data': base_order, 'order_type': 'RESERVE', 'profile': 'UP'}
        stored_order_s = json.dumps(stored_order)
        storage.orders[base_order_id] = stored_order

        worker = Worker(api, storage, profile=Profiles.UP, stock_fee=0.2,
                        spend_profit_markup=0.2)
        worker.main_flow()

        self.assertEqual(2, api.get_open_orders_called)
        self.assertEqual(1, api.create_order_called)
        self.assertTrue(new_order_id in storage.orders)
        self.assertEqual(stored_order_s, json.dumps(storage.orders[base_order_id]))
        self.assertEquals(expected_order, storage.orders[new_order_id]['order_data'])
        self.assertEquals('UP', storage.orders[new_order_id]['profile'])
        self.assertEquals('PROFIT', storage.orders[new_order_id]['order_type'])
        self.assertEquals('OPEN', storage.orders[new_order_id]['status'])

    def test_main_flow_create_profit_order_down(self):
        # Проверяем создание ордера на резерв
        base_order_id = '100'
        base_order = {'order_id': base_order_id, 'quantity': 50, 'price': 100, 'type': 'sell'}
        new_order_id = '122'
        expected_order_type = 'buy'
        expected_price = 53.3333
        expected_quantity = 75
        expected_order = {'order_id': new_order_id, 'quantity': str(expected_quantity), 'price': str(expected_price),
                          'type': expected_order_type}

        class ApiMock:
            def __init__(self, test):
                self.get_open_orders_called = 0
                self.create_order_called = 0
                self.test = test
                self.orders = []

            def get_open_orders(self, currency_1, currency_2):
                    self.get_open_orders_called += 1
                    return self.orders

            def create_order(self, currency_1, currency_2, quantity, price, type):
                self.test.assertEqual('BTC', currency_1)
                self.test.assertEqual('USD', currency_2)
                self.test.assertEqual(expected_quantity, quantity)
                self.test.assertAlmostEqual(expected_price, price, 4)
                self.test.assertEqual(expected_order_type, type)
                    self.create_order_called += 1
                self.orders.append(expected_order)
                return new_order_id

        api = ApiMock(self)

        storage = StorageMock()
        stored_order = {'status': 'WAIT_FOR_PROFIT', 'order_data': base_order, 'order_type': 'RESERVE',
                        'profile': 'DOWN'}
        stored_order_s = json.dumps(stored_order)
        storage.orders[base_order_id] = stored_order

        worker = Worker(api, storage, profile=Profiles.DOWN, stock_fee=0.2,
                        spend_profit_markup=0.2)
        worker.main_flow()

        self.assertEqual(2, api.get_open_orders_called)
        self.assertEqual(1, api.create_order_called)
        self.assertTrue(new_order_id in storage.orders)
        self.assertEqual(stored_order_s, json.dumps(storage.orders[base_order_id]))
        self.assertEquals(expected_order, storage.orders[new_order_id]['order_data'])
        self.assertEquals('DOWN', storage.orders[new_order_id]['profile'])
        self.assertEquals('PROFIT', storage.orders[new_order_id]['order_type'])
        self.assertEquals('OPEN', storage.orders[new_order_id]['status'])

    def test_main_flow_profit_order_completed_up(self):
        # Проверяем, что процесс выходит, если есть не истекший ордер на запас
        mock_order_id = '122'
        order = {'type': 'sell', 'order_id': mock_order_id}
        base_order_id = '100'
        base_order = {'order_id': base_order_id, 'quantity': 50, 'price': 100, 'type': 'buy'}

        class ApiMock:
            def __init__(self, test):
                self.get_open_orders_called = 0
                self.test = test

            def get_open_orders(self, currency_1, currency_2):
                self.get_open_orders_called += 1
                return []

        api = ApiMock(self)

        storage = StorageMock()
        stored_order = {'status': 'OPEN', 'order_data': order, 'order_type': 'PROFIT', 'profile': 'UP',
                        'base_order': base_order}
        stored_base_order = {'status': 'PROFIT_ORDER_CREATED', 'order_data': base_order, 'order_type': 'RESERVE',
                             'profile': 'UP'}
        storage.orders[mock_order_id] = stored_order
        storage.orders[base_order_id] = stored_base_order

        worker = Worker(api, storage, profile=Profiles.UP)
        self.assertRaises(Worker.ScriptQuitCondition, worker.main_flow)

        self.assertEqual(1, api.get_open_orders_called)
        self.assertEqual(0, len(storage.orders))
        self.assertEquals('COMPLETED', storage.archive[mock_order_id])
        self.assertEquals('COMPLETED', storage.archive[base_order_id])

    def test_main_flow_profit_order_completed_down(self):
        # Проверяем, что процесс выходит, если есть не истекший ордер на запас
        mock_order_id = '122'
        order = {'type': 'buy', 'order_id': mock_order_id}
        base_order_id = '100'
        base_order = {'order_id': base_order_id, 'quantity': 50, 'price': 100, 'type': 'sell'}

        class ApiMock:
            def __init__(self, test):
                self.get_open_orders_called = 0
                self.test = test

            def get_open_orders(self, currency_1, currency_2):
                self.get_open_orders_called += 1
                return []

        api = ApiMock(self)

        storage = StorageMock()
        stored_order = {'status': 'OPEN', 'order_data': order, 'order_type': 'PROFIT', 'profile': 'DOWN',
                        'base_order': base_order}
        stored_base_order = {'status': 'PROFIT_ORDER_CREATED', 'order_data': base_order, 'order_type': 'RESERVE',
                             'profile': 'DOWN'}
        storage.orders[mock_order_id] = stored_order
        storage.orders[base_order_id] = stored_base_order

        worker = Worker(api, storage, profile=Profiles.DOWN)
        self.assertRaises(Worker.ScriptQuitCondition, worker.main_flow)

        self.assertEqual(1, api.get_open_orders_called)
        self.assertEqual(0, len(storage.orders))
        self.assertEquals('COMPLETED', storage.archive[mock_order_id])
        self.assertEquals('COMPLETED', storage.archive[base_order_id])


if __name__ == "__main__":
    unittest.main()
